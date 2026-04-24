using System;
using System.Collections.Generic;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Geometry;

namespace InterferenceCheck.Core
{
    /// <summary>
    /// 지정된 레이어의 Solid3d 및 BlockReference를 수집한다.
    /// </summary>
    public class ObjectCollector
    {
        private readonly Database _db;

        public ObjectCollector(Database db) => _db = db;

        // ─────────────────────────────────────────────
        // 공개 API
        // ─────────────────────────────────────────────

        public List<string> GetAllLayerNames()
        {
            var result = new List<string>();
            using (var tr = _db.TransactionManager.StartOpenCloseTransaction())
            {
                var lt = (LayerTable)tr.GetObject(_db.LayerTableId, OpenMode.ForRead);
                foreach (ObjectId id in lt)
                {
                    var ltr = (LayerTableRecord)tr.GetObject(id, OpenMode.ForRead);
                    if (!ltr.IsErased)
                        result.Add(ltr.Name);
                }
                tr.Commit();
            }
            result.Sort(StringComparer.OrdinalIgnoreCase);
            return result;
        }

        public List<EntityInfo> CollectFromLayers(IEnumerable<string> layerNames)
        {
            var layerSet = new HashSet<string>(layerNames, StringComparer.OrdinalIgnoreCase);
            var result   = new List<EntityInfo>();

            using (var tr = _db.TransactionManager.StartOpenCloseTransaction())
            {
                var ms = (BlockTableRecord)tr.GetObject(
                    SymbolUtilityServices.GetBlockModelSpaceId(_db), OpenMode.ForRead);

                foreach (ObjectId id in ms)
                {
                    Entity ent;
                    try { ent = (Entity)tr.GetObject(id, OpenMode.ForRead); }
                    catch { continue; }

                    if (!layerSet.Contains(ent.Layer)) continue;

                    EntityInfo info = null;

                    if (ent is Solid3d solid)
                        info = BuildSolidInfo(id, solid);
                    else if (ent is BlockReference bref)
                        info = BuildBlockInfo(id, bref, tr);

                    if (info != null)
                        result.Add(info);
                }
                tr.Commit();
            }
            return result;
        }

        // ─────────────────────────────────────────────
        // 내부 빌더
        // ─────────────────────────────────────────────

        private EntityInfo BuildSolidInfo(ObjectId id, Solid3d solid)
        {
            Extents3d ext;
            try   { ext = solid.GeometricExtents; }
            catch { return null; }

            var handle = solid.Handle.ToString();
            var layer  = solid.Layer;

            return new EntityInfo
            {
                Id              = id,
                DisplayName     = $"Solid3d [{handle}]",
                LayerName       = layer,
                BoundingBox     = ext,
                IsBlockReference= false,
                GetWorldSolids  = () => CloneSingleSolid(id)
            };
        }

        private EntityInfo BuildBlockInfo(ObjectId id, BlockReference bref, Transaction tr)
        {
            Extents3d ext;
            try   { ext = bref.GeometricExtents; }
            catch { return null; }

            // 블럭 내부에 Solid3d가 있는지 빠르게 확인
            var defId     = bref.BlockTableRecord;
            var transform = bref.BlockTransform;
            var blockName = bref.Name;
            var handle    = bref.Handle.ToString();
            var layer     = bref.Layer;

            return new EntityInfo
            {
                Id               = id,
                DisplayName      = $"Block: {blockName} [{handle}]",
                LayerName        = layer,
                BoundingBox      = ext,
                IsBlockReference = true,
                BlockName        = blockName,
                GetWorldSolids   = () => ExtractSolidsFromBlock(defId, transform)
            };
        }

        // ─────────────────────────────────────────────
        // 솔리드 추출/복제 헬퍼
        // ─────────────────────────────────────────────

        private List<Solid3d> CloneSingleSolid(ObjectId id)
        {
            var list = new List<Solid3d>();
            using (var tr = _db.TransactionManager.StartOpenCloseTransaction())
            {
                if (tr.GetObject(id, OpenMode.ForRead) is Solid3d solid)
                {
                    var clone = (Solid3d)solid.Clone();
                    list.Add(clone);
                }
                tr.Commit();
            }
            return list;
        }

        private List<Solid3d> ExtractSolidsFromBlock(ObjectId btrId, Matrix3d parentXform)
        {
            var solids = new List<Solid3d>();
            using (var tr = _db.TransactionManager.StartOpenCloseTransaction())
            {
                CollectSolidsRecursive(tr, btrId, parentXform, solids);
                tr.Commit();
            }
            return solids;
        }

        private void CollectSolidsRecursive(Transaction tr, ObjectId btrId,
            Matrix3d xform, List<Solid3d> result)
        {
            var btr = tr.GetObject(btrId, OpenMode.ForRead) as BlockTableRecord;
            if (btr == null) return;

            foreach (ObjectId id in btr)
            {
                Entity ent;
                try { ent = (Entity)tr.GetObject(id, OpenMode.ForRead); }
                catch { continue; }

                if (ent is Solid3d solid)
                {
                    var clone = (Solid3d)solid.Clone();
                    clone.TransformBy(xform);
                    result.Add(clone);
                }
                else if (ent is BlockReference nested)
                {
                    var combined = xform * nested.BlockTransform;
                    CollectSolidsRecursive(tr, nested.BlockTableRecord, combined, result);
                }
            }
        }
    }
}
