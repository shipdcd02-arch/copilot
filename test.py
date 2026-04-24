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
        [CommandMethod("MAKESECTIONBLOCK")]
        public void MakeSectionBlock()
        {
            var doc = Application.DocumentManager.MdiActiveDocument;
            var db = doc.Database;
            var ed = doc.Editor;

            var res = ed.GetPoint("\n섹션 위치 지정 (점 하나): ");
            if (res.Status != PromptStatus.OK) return;

            var pt = res.Value;

            // XZ 평면 섹션: Y좌표 고정, X축 방향으로 절단선
            var pt1 = new Point3d(-1000000, pt.Y, 0);
            var pt2 = new Point3d( 1000000, pt.Y, 0);

            using (var tr = db.TransactionManager.StartTransaction())
            {
                var bt = (BlockTable)tr.GetObject(db.BlockTableId, OpenMode.ForRead);
                var ms = (BlockTableRecord)tr.GetObject(
                    bt[BlockTableRecord.ModelSpace], OpenMode.ForWrite);

                // 섹션 플레인 생성 및 DB에 먼저 추가
                var section = new Section();
                section.SetDatabaseDefaults();
                var sectionId = ms.AppendEntity(section);
                tr.AddNewlyCreatedDBObject(section, true);

                // DB 추가 후 설정
                section.UpgradeOpen();
                section.AddVertex(0, pt1);
                section.AddVertex(1, pt2);

                // XZ 평면: Y축 방향으로 바라봄
                section.VerticalDirection = Vector3d.ZAxis;
                section.ViewingDirection  = Vector3d.YAxis;
                section.TopPlane    =  100000;
                section.BottomPlane = -100000;

                // 모든 객체에 섹션 지오메트리 생성
                var collected = new List<Entity>();

                foreach (ObjectId id in ms)
                {
                    if (id == sectionId) continue;
                    var ent = tr.GetObject(id, OpenMode.ForRead) as Entity;
                    if (ent == null) continue;

                    try
                    {
                        section.GenerateSectionGeometry(
                            ent,
                            out Array intFillEnts,
                            out Array bgEnts,
                            out Array fgEnts,
                            out Array furveTang,
                            out Array curveTang
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

                // 임시 섹션 플레인 삭제
                section.Erase();

                if (collected.Count == 0)
                {
                    ed.WriteMessage("\n생성된 섹션 지오메트리가 없습니다.");
                    tr.Commit();
                    return;
                }

                // 블록 생성
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