using System;
using System.Windows.Interop;
using Autodesk.AutoCAD.Runtime;
using Autodesk.AutoCAD.ApplicationServices;
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

            ed.WriteMessage("\n===== 간섭 검사 (InterferenceCheck) =====\n");

            // ── 레이어 목록 수집 ──────────────────────────
            var collector = new ObjectCollector(db);
            var layers    = collector.GetAllLayerNames();

            if (layers.Count == 0)
            {
                ed.WriteMessage("\n레이어가 없습니다. 명령을 종료합니다.\n");
                return;
            }

            // ── 그룹1 레이어 선택 ─────────────────────────
            var dlg1 = new LayerSelectionDialog(layers, "그룹1 레이어 선택 (기준 그룹)");
            SetOwner(dlg1);
            if (dlg1.ShowDialog() != true) { ed.WriteMessage("\n취소되었습니다.\n"); return; }
            var layers1 = dlg1.SelectedLayers;

            // ── 그룹2 레이어 선택 ─────────────────────────
            var dlg2 = new LayerSelectionDialog(layers, "그룹2 레이어 선택 (비교 그룹)");
            SetOwner(dlg2);
            if (dlg2.ShowDialog() != true) { ed.WriteMessage("\n취소되었습니다.\n"); return; }
            var layers2 = dlg2.SelectedLayers;

            ed.WriteMessage($"\n그룹1: {string.Join(", ", layers1)}");
            ed.WriteMessage($"\n그룹2: {string.Join(", ", layers2)}");
            ed.WriteMessage("\n객체 수집 중...\n");

            // ── 엔티티 수집 ───────────────────────────────
            var group1 = collector.CollectFromLayers(layers1);
            var group2 = collector.CollectFromLayers(layers2);

            ed.WriteMessage($"그룹1: {group1.Count}개, 그룹2: {group2.Count}개 객체 발견\n");

            if (group1.Count == 0 || group2.Count == 0)
            {
                ed.WriteMessage("검사 대상 객체(Solid3d 또는 BlockReference)가 없습니다.\n");
                return;
            }

            // ── 결과 다이얼로그 (검사 포함) ───────────────
            var resultDlg = new InterferenceResultDialog(group1, group2, db);
            SetOwner(resultDlg);
            resultDlg.ShowDialog();

            ed.WriteMessage("\n간섭 검사 완료.\n");
        }

        private static void SetOwner(System.Windows.Window window)
        {
            try
            {
                var helper = new WindowInteropHelper(window);
                helper.Owner = AcadApp.MainWindow.Handle;
            }
            catch { /* 오너 설정 실패 시 무시 */ }
        }
    }
}
