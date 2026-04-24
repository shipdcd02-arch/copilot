using System;
using System.Collections.Generic;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.EditorInput;
using Autodesk.AutoCAD.Geometry;
using Autodesk.AutoCAD.Runtime;

namespace SectionAutoBlock
{
    public class Commands
    {
        [CommandMethod("AUTOSECTIONBLOCK")]
        public void AutoSectionToBlock()
        {
            var doc = Application.DocumentManager.MdiActiveDocument;
            var db = doc.Database;
            var ed = doc.Editor;

            var res = ed.GetEntity("\n섹션 플레인 선택: ");
            if (res.Status != PromptStatus.OK) return;

            using (var tr = db.TransactionManager.StartTransaction())
            {
                var section = (Section)tr.GetObject(res.ObjectId, OpenMode.ForRead);
                var bt = (BlockTable)tr.GetObject(db.BlockTableId, OpenMode.ForRead);
                var modelSpace = (BlockTableRecord)tr.GetObject(
                    bt[BlockTableRecord.ModelSpace], OpenMode.ForRead);

                var collected = new List<Entity>();

                // 모델스페이스의 모든 객체에 대해 섹션 지오메트리 생성
                foreach (ObjectId id in modelSpace)
                {
                    var ent = tr.GetObject(id, OpenMode.ForRead) as Entity;
                    if (ent == null || ent is Section) continue;

                    Array intFillEnts = null;
                    Array bgEnts     = null;
                    Array fgEnts     = null;
                    Array furveTang  = null;
                    Array curveTang  = null;

                    try
                    {
                        section.GenerateSectionGeometry(
                            ent,
                            ref intFillEnts,
                            ref bgEnts,
                            ref fgEnts,
                            ref furveTang,
                            ref curveTang
                        );

                        void Collect(Array arr)
                        {
                            if (arr == null) return;
                            foreach (Entity e in arr)
                                if (e != null) collected.Add(e);
                        }

                        Collect(fgEnts);
                        Collect(bgEnts);
                        Collect(intFillEnts);
                        Collect(curveTang);
                    }
                    catch { }
                }

                if (collected.Count == 0)
                {
                    ed.WriteMessage("\n생성된 섹션 지오메트리가 없습니다.");
                    return;
                }

                // 새 블록 생성
                string blockName = "SEC_" + DateTime.Now.ToString("yyyyMMdd_HHmmss");
                var newBtr = new BlockTableRecord { Name = blockName };

                var btWrite = (BlockTable)tr.GetObject(db.BlockTableId, OpenMode.ForWrite);
                var newBtrId = btWrite.Add(newBtr);
                tr.AddNewlyCreatedDBObject(newBtr, true);

                foreach (var e in collected)
                {
                    newBtr.AppendEntity(e);
                    tr.AddNewlyCreatedDBObject(e, true);
                }

                // 모델스페이스에 블록 참조 삽입
                var msWrite = (BlockTableRecord)tr.GetObject(
                    bt[BlockTableRecord.ModelSpace], OpenMode.ForWrite);
                var blkRef = new BlockReference(Point3d.Origin, newBtrId);
                msWrite.AppendEntity(blkRef);
                tr.AddNewlyCreatedDBObject(blkRef, true);

                ed.WriteMessage($"\n블록 '{blockName}' 생성 완료 ({collected.Count}개 객체)");
                tr.Commit();
            }
        }
    }
}