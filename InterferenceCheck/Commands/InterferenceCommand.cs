using System;
using System.Collections.Generic;
using System.IO;
using System.Windows.Interop;
using Autodesk.AutoCAD.Runtime;
using AcRuntimeException = Autodesk.AutoCAD.Runtime.Exception;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.EditorInput;
using Autodesk.AutoCAD.Geometry;
using InterferenceCheck.Core;
using InterferenceCheck.Dialogs;
using AcadApp = Autodesk.AutoCAD.ApplicationServices.Application;

[assembly: CommandClass(typeof(InterferenceCheck.Commands.InterferenceCommand))]

namespace InterferenceCheck.Commands
{
    public class InterferenceCommand
    {
        // 결과 창을 멤버로 유지 (모달리스이므로 GC 방지)
        private static InterferenceResultDialog _resultDlg;

        // ─────────────────────────────────────────────────
        // 메인 명령어
        // ─────────────────────────────────────────────────
        [CommandMethod("INTERCHECK", CommandFlags.Modal)]
        public void RunInterferenceCheck()
        {
            var doc = AcadApp.DocumentManager.MdiActiveDocument;
            if (doc == null) return;
            var db = doc.Database;
            var ed = doc.Editor;

            ed.WriteMessage("\n===== INTERCHECK =====\n");

            var collector = new ObjectCollector(db);
            var layers    = collector.GetAllLayerNames();
            if (layers.Count == 0) { ed.WriteMessage("레이어 없음.\n"); return; }

            // 그룹 1
            var dlg1 = new LayerSelectionDialog(layers, "그룹1 레이어 선택 (기준)");
            SetOwner(dlg1);
            if (dlg1.ShowDialog() != true) return;

            // 그룹 2
            var dlg2 = new LayerSelectionDialog(layers, "그룹2 레이어 선택 (비교)");
            SetOwner(dlg2);
            if (dlg2.ShowDialog() != true) return;

            // 객체 수집
            var group1 = collector.CollectFromLayers(dlg1.SelectedLayers);
            var group2 = collector.CollectFromLayers(dlg2.SelectedLayers);
            ed.WriteMessage($"수집: 그룹1 {group1.Count}개 / 그룹2 {group2.Count}개\n");

            if (group1.Count == 0 || group2.Count == 0)
            {
                ed.WriteMessage("검사 대상 없음 (Solid3d / BlockReference).\n");
                return;
            }

            // 간섭 검사 (명령 스레드 동기 실행)
            ed.WriteMessage("검사 중...\n");
            var engine = new InterferenceEngine { MinVolume = 0.001, AabbTolerance = 0.0 };
            engine.StatusChanged += msg => ed.WriteMessage($"  {msg}\n");

            var (results, stats) = engine.CheckInterference(group1, group2);
            ed.WriteMessage($"결과: {results.Count}건  /  {stats.ElapsedSeconds:F1}초\n");
            ed.WriteMessage($"  AABB통과={stats.AabbCandidates}  Boolean={stats.BoolOpPerformed}\n");

            // 모달리스 결과 창 (이미 열려있으면 닫기)
            _resultDlg?.Close();
            _resultDlg = new InterferenceResultDialog(
                results, stats, group1, group2, db,
                recheckCallback: newMinVol =>
                {
                    ed.WriteMessage($"\n[재검사] MinVolume={newMinVol}\n");
                    engine.MinVolume = newMinVol;
                    var (r2, s2) = engine.CheckInterference(group1, group2);
                    ed.WriteMessage($"재검사 결과: {r2.Count}건\n");
                    return (r2, s2);
                });
            SetOwner(_resultDlg);
            _resultDlg.Show(); // 모달리스 - AutoCAD 조작 가능
        }

        // ─────────────────────────────────────────────────
        // 진단 명령어: 두 객체를 직접 선택해서 Boolean 결과 확인
        // ─────────────────────────────────────────────────
        [CommandMethod("INTERCHECK_TEST", CommandFlags.Modal)]
        public void TestInterference()
        {
            var doc = AcadApp.DocumentManager.MdiActiveDocument;
            var db  = doc.Database;
            var ed  = doc.Editor;
            var log = new List<string>();
            void L(string s) { ed.WriteMessage(s + "\n"); log.Add(s); }

            L("\n===== INTERCHECK_TEST =====");

            // 첫 번째 객체 선택
            var opt1 = new PromptEntityOptions("\n[1] 첫 번째 Solid3d 선택: ");
            opt1.SetRejectMessage("Solid3d를 선택하세요.");
            opt1.AddAllowedClass(typeof(Solid3d), true);
            var res1 = ed.GetEntity(opt1);
            if (res1.Status != PromptStatus.OK) return;

            // 두 번째 객체 선택
            var opt2 = new PromptEntityOptions("\n[2] 두 번째 Solid3d 선택: ");
            opt2.SetRejectMessage("Solid3d를 선택하세요.");
            opt2.AddAllowedClass(typeof(Solid3d), true);
            var res2 = ed.GetEntity(opt2);
            if (res2.Status != PromptStatus.OK) return;

            using (var tr = db.TransactionManager.StartOpenCloseTransaction())
            {
                var s1 = tr.GetObject(res1.ObjectId, OpenMode.ForRead) as Solid3d;
                var s2 = tr.GetObject(res2.ObjectId, OpenMode.ForRead) as Solid3d;

                if (s1 == null || s2 == null) { L("Solid3d 아님"); return; }

                // AABB 확인
                Extents3d e1 = s1.GeometricExtents;
                Extents3d e2 = s2.GeometricExtents;
                L($"[S1] BBox Min=({e1.MinPoint.X:F2},{e1.MinPoint.Y:F2},{e1.MinPoint.Z:F2})");
                L($"     BBox Max=({e1.MaxPoint.X:F2},{e1.MaxPoint.Y:F2},{e1.MaxPoint.Z:F2})");
                L($"[S2] BBox Min=({e2.MinPoint.X:F2},{e2.MinPoint.Y:F2},{e2.MinPoint.Z:F2})");
                L($"     BBox Max=({e2.MaxPoint.X:F2},{e2.MaxPoint.Y:F2},{e2.MaxPoint.Z:F2})");

                bool aabb =
                    e1.MinPoint.X <= e2.MaxPoint.X && e1.MaxPoint.X >= e2.MinPoint.X &&
                    e1.MinPoint.Y <= e2.MaxPoint.Y && e1.MaxPoint.Y >= e2.MinPoint.Y &&
                    e1.MinPoint.Z <= e2.MaxPoint.Z && e1.MaxPoint.Z >= e2.MinPoint.Z;
                L($"AABB 중첩: {aabb}");

                // Boolean 시도
                Solid3d c1 = null, c2 = null;
                bool consumed = false;
                try
                {
                    c1 = (Solid3d)s1.Clone();
                    c2 = (Solid3d)s2.Clone();
                    c1.BooleanOperation(BooleanOperationType.BoolIntersect, c2);
                    consumed = true;

                    double vol;
                    try   { vol = c1.MassProperties.Volume; }
                    catch (System.Exception ex) { L($"MassProperties 오류: {ex.Message}"); vol = -1; }

                    L($"Boolean 교차 체적: {vol:G6}");
                    L(vol > 0.001 ? ">>> 간섭 있음!" : ">>> 간섭 없음 (체적 부족)");
                }
                catch (System.Exception ex)
                {
                    L($"BooleanOperation 예외: {ex.Message}");
                    L(">>> Boolean 연산 실패 (접촉만 하거나 기하 오류)");
                }
                finally
                {
                    c1?.Dispose();
                    if (!consumed) c2?.Dispose();
                }

                tr.Commit();
            }

            // 로그 파일 저장
            try
            {
                string path = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.Desktop),
                    "INTERCHECK_DEBUG.txt");
                File.WriteAllLines(path, log);
                ed.WriteMessage($"로그 저장: {path}\n");
            }
            catch { }
        }

        private static void SetOwner(System.Windows.Window w)
        {
            try { new WindowInteropHelper(w).Owner = AcadApp.MainWindow.Handle; }
            catch { }
        }
    }
}
