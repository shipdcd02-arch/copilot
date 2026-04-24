using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.EditorInput;
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

            var opt = new PromptEntityOptions("\n섹션 플레인 선택: ");
            opt.SetRejectMessage("\n섹션 플레인만 선택하세요.");
            opt.AddAllowedClass(typeof(Section), true);

            var res = ed.GetEntity(opt);
            if (res.Status != PromptStatus.OK) return;

            using (var tr = db.TransactionManager.StartTransaction())
            {
                var section = (Section)tr.GetObject(res.ObjectId, OpenMode.ForRead);
                var ids = new ObjectIdCollection();

                section.GenerateGeometry(SectionType.Section2dType, ids);

                ed.WriteMessage($"\n완료: {ids.Count}개 객체 생성됨");
                tr.Commit();
            }
        }
    }
}