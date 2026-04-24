using System;
using System.Windows.Interop;
using Autodesk.AutoCAD.Runtime;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.EditorInput;
using InterferenceCheck.Core;
using InterferenceCheck.Dialogs;
using AcadApp = Autodesk.AutoCAD.ApplicationServices.Application;

[assembly: CommandClass(typeof(InterferenceCheck.Commands.InterferenceCommand))]

namespace InterferenceCheck.Commands
{
    public class InterferenceCommand
    {
        [CommandMethod("INTERCHECK", CommandFlags.Modal)]
        public void RunInterferenceCheck()
        {
            var doc = AcadApp.DocumentManager.MdiActiveDocument;
            if (doc == null) return;

            var db = doc.Database;
            var ed = doc.Editor;

            ed.WriteMessage("\n===== InterferenceCheck =====\n");

            // ── 레이어 목록 ──────────────────────────────
            var collector = new ObjectCollector(db);
            var layers    = collector.GetAllLayerNames();
            if (layers.Count == 0) { ed.WriteMessage("\n레이어 없음.\n"); return; }

            // ── 그룹1 선택 ───────────────────────────────
            var dlg1 = new LayerSelectionDialog(layers, "그룹1 레이어 선택 (기준 그룹)");
            SetOwner(dlg1);
            if (dlg1.ShowDialog() != true) return;

            // ── 그룹2 선택 ───────────────────────────────
            var dlg2 = new LayerSelectionDialog(layers, "그룹2 레이어 선택 (비교 그룹)");
            SetOwner(dlg2);
            if (dlg2.ShowDialog() != true) return;

            ed.WriteMessage($"\n그룹1: {string.Join(", ", dlg1.SelectedLayers)}");
            ed.WriteMessage($"\n그룹2: {string.Join(", ", dlg2.SelectedLayers)}");
            ed.WriteMessage("\n객체 수집 중...\n");

            // ── 객체 수집 ────────────────────────────────
            var group1 = collector.CollectFromLayers(dlg1.SelectedLayers);
            var group2 = collector.CollectFromLayers(dlg2.SelectedLayers);
            ed.WriteMessage($"그룹1: {group1.Count}개  /  그룹2: {group2.Count}개\n");

            if (group1.Count == 0 || group2.Count == 0)
            {
                ed.WriteMessage("검사 대상(Solid3d / BlockReference) 없음.\n");
                return;
            }

            // ── 간섭 검사 (명령 스레드에서 동기 실행) ────
            ed.WriteMessage("간섭 검사 중... (완료까지 AutoCAD가 잠시 멈출 수 있습니다)\n");

            var engine = new InterferenceEngine
            {
                MinVolume     = 0.001,
                AabbTolerance = 0.0
            };

            int reportStep = Math.Max(1, (group1.Count * group2.Count) / 20);
            int pairIdx    = 0;
            engine.StatusChanged   += msg => { };   // 커맨드라인 출력 최소화
            engine.ProgressChanged += (cur, total) =>
            {
                pairIdx++;
                if (pairIdx % reportStep == 0)
                    ed.WriteMessage($"  {cur}/{total} 쌍 검사 중...\r");
            };

            var (results, stats) = engine.CheckInterference(group1, group2);

            ed.WriteMessage($"\n완료: {results.Count}건 발견 / {stats.ElapsedSeconds:F1}초\n");
            ed.WriteMessage($"  AABB 통과: {stats.AabbCandidates}쌍 / Boolean 연산: {stats.BoolOpPerformed}회\n");

            // ── 결과 다이얼로그 ──────────────────────────
            var resultDlg = new InterferenceResultDialog(results, stats, group1, group2, db,
                recheckCallback: (newMinVol) =>
                {
                    // 재검사: 다이얼로그에서 임계값 변경 후 호출
                    engine.MinVolume = newMinVol;
                    return engine.CheckInterference(group1, group2);
                });
            SetOwner(resultDlg);
            resultDlg.ShowDialog();

            ed.WriteMessage("\n간섭 검사 완료.\n");
        }

        private static void SetOwner(System.Windows.Window w)
        {
            try { new WindowInteropHelper(w).Owner = AcadApp.MainWindow.Handle; }
            catch { }
        }
    }
}
