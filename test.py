using System;
using System.Reflection;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.EditorInput;
using Autodesk.AutoCAD.Runtime;

namespace SectionAutoBlock
{
    public class Commands
    {
        [CommandMethod("DUMPSECTION")]
        public void DumpSection()
        {
            var doc = Application.DocumentManager.MdiActiveDocument;
            var ed = doc.Editor;

            var res = ed.GetEntity("\n섹션 플레인 선택: ");
            if (res.Status != PromptStatus.OK) return;

            using (var tr = doc.Database.TransactionManager.StartTransaction())
            {
                var obj = tr.GetObject(res.ObjectId, OpenMode.ForRead);
                var type = obj.GetType();

                // GenerateSectionGeometry 파라미터만 출력
                foreach (var method in type.GetMethods())
                {
                    if (method.Name == "GenerateSectionGeometry")
                    {
                        ed.WriteMessage($"\n오버로드:");
                        foreach (var param in method.GetParameters())
                        {
                            ed.WriteMessage($"\n  [{param.ParameterType.FullName}] {param.Name}");
                        }
                        ed.WriteMessage("\n---");
                    }
                }

                tr.Commit();
            }
        }
    }
}