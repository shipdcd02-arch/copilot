using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.IO;
using System.Linq;
using System.Text;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Geometry;
using InterferenceCheck.Core;
using InterferenceCheck.Models;
using AcadApp = Autodesk.AutoCAD.ApplicationServices.Application;

namespace InterferenceCheck.Dialogs
{
    public partial class InterferenceResultDialog : Window
    {
        // ── 데이터 ───────────────────────────────────────
        private readonly List<EntityInfo>    _group1;
        private readonly List<EntityInfo>    _group2;
        private readonly Database            _db;
        private readonly Func<double, (List<InterferenceResult>, CheckStatistics)> _recheckCallback;

        private List<InterferenceResult>             _allResults;
        private ObservableCollection<InterferenceResult> _filtered;
        private Dictionary<ObjectId, int>            _originalColors = new Dictionary<ObjectId, int>();

        // ── TreeView 모델 ─────────────────────────────────
        private class TreeNode
        {
            public string              Label      { get; set; }
            public string              CountLabel { get; set; }
            public List<TreeNode>      Children   { get; set; } = new List<TreeNode>();
            public List<InterferenceResult> Results { get; set; }
        }

        // ─────────────────────────────────────────────────
        public InterferenceResultDialog(
            List<InterferenceResult> results,
            CheckStatistics stats,
            List<EntityInfo> group1,
            List<EntityInfo> group2,
            Database db,
            Func<double, (List<InterferenceResult>, CheckStatistics)> recheckCallback)
        {
            InitializeComponent();
            _allResults      = results ?? new List<InterferenceResult>();
            _group1          = group1;
            _group2          = group2;
            _db              = db;
            _recheckCallback = recheckCallback;
            _filtered        = new ObservableCollection<InterferenceResult>();
            ResultListView.ItemsSource = _filtered;
        }

        private void Window_Loaded(object sender, RoutedEventArgs e)
        {
            Refresh();
        }

        private void Refresh()
        {
            PopulateStats(null);   // 통계는 _allResults 기준
            BuildTree();
            ApplyFilter();
            SetButtonsEnabled();
        }

        // ── 통계 ─────────────────────────────────────────
        private void PopulateStats(CheckStatistics s)
        {
            int total = _allResults.Count;
            StatFound.Text  = $"간섭 발견: {total}건";
            StatG1.Text     = $"그룹1: {_group1?.Count ?? 0}개";
            StatG2.Text     = $"그룹2: {_group2?.Count ?? 0}개";
            StatPairs.Text  = s != null ? $"총 쌍: {s.TotalPairs}" : "";
            StatBool.Text   = s != null ? $"Boolean: {s.BoolOpPerformed}회" : "";
            StatTime.Text   = s != null ? $"{s.ElapsedSeconds:F1}초" : "";
        }

        // ── 트리 ─────────────────────────────────────────
        private void BuildTree()
        {
            var nodes = new List<TreeNode>
            {
                new TreeNode
                {
                    Label      = "전체",
                    CountLabel = $" ({_allResults.Count}건)",
                    Results    = _allResults
                }
            };

            foreach (var g1grp in _allResults.GroupBy(r => r.Group1Entity.LayerName).OrderBy(g => g.Key))
            {
                var g1 = new TreeNode
                {
                    Label      = $"[G1] {g1grp.Key}",
                    CountLabel = $" ({g1grp.Count()}건)",
                    Results    = g1grp.ToList()
                };
                foreach (var g2grp in g1grp.GroupBy(r => r.Group2Entity.LayerName).OrderBy(g => g.Key))
                {
                    g1.Children.Add(new TreeNode
                    {
                        Label      = $"  → [G2] {g2grp.Key}",
                        CountLabel = $" ({g2grp.Count()}건)",
                        Results    = g2grp.ToList()
                    });
                }
                nodes.Add(g1);
            }

            SummaryTree.ItemsSource = nodes;
        }

        private void SummaryTree_SelectedItemChanged(object sender, RoutedPropertyChangedEventArgs<object> e)
        {
            if (e.NewValue is TreeNode node)
            {
                _filtered.Clear();
                var f = FilterBox.Text.Trim().ToLower();
                foreach (var r in node.Results.Where(r => MatchFilter(r, f)))
                    _filtered.Add(r);
                UpdateListCount();
            }
        }

        // ── 필터 ─────────────────────────────────────────
        private void FilterBox_TextChanged(object sender, TextChangedEventArgs e) => ApplyFilter();

        private void ApplyFilter()
        {
            var f = FilterBox.Text.Trim().ToLower();
            _filtered.Clear();
            foreach (var r in _allResults.Where(r => MatchFilter(r, f)))
                _filtered.Add(r);
            UpdateListCount();
        }

        private bool MatchFilter(InterferenceResult r, string f)
        {
            if (string.IsNullOrEmpty(f)) return true;
            return r.Group1Entity.DisplayName.ToLower().Contains(f)
                || r.Group1Entity.LayerName.ToLower().Contains(f)
                || r.Group2Entity.DisplayName.ToLower().Contains(f)
                || r.Group2Entity.LayerName.ToLower().Contains(f);
        }

        private void UpdateListCount() =>
            ListCountLabel.Text = $"{_filtered.Count}건";

        // ── 선택 이벤트 ──────────────────────────────────
        private void ResultListView_SelectionChanged(object sender, SelectionChangedEventArgs e) =>
            SetButtonsEnabled();

        private void ResultListView_DoubleClick(object sender, MouseButtonEventArgs e) =>
            ZoomToSelected();

        // ── 줌 ───────────────────────────────────────────
        private void BtnZoom_Click(object sender, RoutedEventArgs e) => ZoomToSelected();

        private void ZoomToSelected()
        {
            var sel = ResultListView.SelectedItems.Cast<InterferenceResult>().ToList();
            if (sel.Count == 0) return;

            Extents3d ext = sel[0].Group1Entity.BoundingBox;
            foreach (var r in sel)
            {
                ext.AddExtents(r.Group1Entity.BoundingBox);
                ext.AddExtents(r.Group2Entity.BoundingBox);
            }

            var doc = AcadApp.DocumentManager.MdiActiveDocument;
            try
            {
                using (doc.LockDocument())
                {
                    var view  = doc.Editor.GetCurrentView();
                    double w  = Math.Max((ext.MaxPoint.X - ext.MinPoint.X) * 1.4, 0.001);
                    double h  = Math.Max((ext.MaxPoint.Y - ext.MinPoint.Y) * 1.4, 0.001);
                    double ar = view.Width / Math.Max(view.Height, 0.001);
                    if (w / h < ar) w = h * ar; else h = w / ar;

                    view.CenterPoint = new Point2d(
                        (ext.MinPoint.X + ext.MaxPoint.X) / 2,
                        (ext.MinPoint.Y + ext.MaxPoint.Y) / 2);
                    view.Width  = w;
                    view.Height = h;
                    doc.Editor.SetCurrentView(view);
                }
            }
            catch (Exception ex) { MessageBox.Show($"줌 오류: {ex.Message}"); }
        }

        // ── 선택 하이라이트 ───────────────────────────────
        private void BtnHighlight_Click(object sender, RoutedEventArgs e)
        {
            var ids = ResultListView.SelectedItems.Cast<InterferenceResult>()
                .SelectMany(r => new[] { r.Group1Entity.Id, r.Group2Entity.Id })
                .Distinct().ToArray();
            if (ids.Length == 0) return;

            try
            {
                using (AcadApp.DocumentManager.MdiActiveDocument.LockDocument())
                    AcadApp.DocumentManager.MdiActiveDocument.Editor.SetImpliedSelection(ids);
            }
            catch (Exception ex) { MessageBox.Show($"선택 오류: {ex.Message}"); }
        }

        // ── 색상 변경 / 복원 ─────────────────────────────
        private void BtnChangeColor_Click(object sender, RoutedEventArgs e)
        {
            var ids = ResultListView.SelectedItems.Cast<InterferenceResult>()
                .SelectMany(r => new[] { r.Group1Entity.Id, r.Group2Entity.Id })
                .Distinct().ToList();
            if (ids.Count == 0) return;
            ChangeColors(ids, 1);
            BtnRestoreColor.IsEnabled = true;
        }

        private void BtnRestoreColor_Click(object sender, RoutedEventArgs e)
        {
            if (_originalColors.Count == 0) return;
            var doc = AcadApp.DocumentManager.MdiActiveDocument;
            try
            {
                using (doc.LockDocument())
                using (var tr = _db.TransactionManager.StartOpenCloseTransaction())
                {
                    foreach (var kv in _originalColors)
                        if (tr.GetObject(kv.Key, OpenMode.ForWrite) is Entity ent)
                            ent.ColorIndex = kv.Value;
                    tr.Commit();
                }
                doc.Editor.Regen();
                _originalColors.Clear();
                BtnRestoreColor.IsEnabled = false;
            }
            catch (Exception ex) { MessageBox.Show($"색상 복원 오류: {ex.Message}"); }
        }

        private void ChangeColors(List<ObjectId> ids, int colorIdx)
        {
            var doc = AcadApp.DocumentManager.MdiActiveDocument;
            try
            {
                using (doc.LockDocument())
                using (var tr = _db.TransactionManager.StartOpenCloseTransaction())
                {
                    foreach (var id in ids)
                        if (tr.GetObject(id, OpenMode.ForWrite) is Entity ent)
                        {
                            if (!_originalColors.ContainsKey(id))
                                _originalColors[id] = ent.ColorIndex;
                            ent.ColorIndex = colorIdx;
                        }
                    tr.Commit();
                }
                doc.Editor.Regen();
            }
            catch (Exception ex) { MessageBox.Show($"색상 변경 오류: {ex.Message}"); }
        }

        // ── 간섭 솔리드 생성 ─────────────────────────────
        private void BtnCreateSolid_Click(object sender, RoutedEventArgs e)
        {
            if (_allResults.Count == 0) return;
            const string layerName = "INTERFERENCE_SOLID";
            var doc = AcadApp.DocumentManager.MdiActiveDocument;
            int created = 0;

            try
            {
                using (doc.LockDocument())
                using (var tr = _db.TransactionManager.StartTransaction())
                {
                    var lt = (LayerTable)tr.GetObject(_db.LayerTableId, OpenMode.ForRead);
                    if (!lt.Has(layerName))
                    {
                        lt.UpgradeOpen();
                        var nl = new LayerTableRecord { Name = layerName };
                        nl.Color = Autodesk.AutoCAD.Colors.Color.FromColorIndex(
                            Autodesk.AutoCAD.Colors.ColorMethod.ByAci, 1);
                        lt.Add(nl);
                        tr.AddNewlyCreatedDBObject(nl, true);
                    }

                    var ms = (BlockTableRecord)tr.GetObject(
                        SymbolUtilityServices.GetBlockModelSpaceId(_db), OpenMode.ForWrite);

                    foreach (var res in _allResults)
                    {
                        List<Solid3d> s1l = null, s2l = null;
                        try
                        {
                            s1l = res.Group1Entity.GetWorldSolids();
                            s2l = res.Group2Entity.GetWorldSolids();
                            if (s1l == null || s2l == null) continue;

                            foreach (var s1 in s1l)
                            foreach (var s2 in s2l)
                            {
                                Solid3d c1 = null, c2 = null;
                                bool consumed = false;
                                try
                                {
                                    c1 = (Solid3d)s1.Clone();
                                    c2 = (Solid3d)s2.Clone();
                                    c1.BooleanOperation(BooleanOperationType.BoolIntersect, c2);
                                    consumed = true;

                                    double vol;
                                    try { vol = c1.MassProperties.Volume; } catch { c1.Dispose(); continue; }
                                    if (vol < 0.001) { c1.Dispose(); continue; }

                                    c1.Layer      = layerName;
                                    c1.ColorIndex = 1;
                                    ms.AppendEntity(c1);
                                    tr.AddNewlyCreatedDBObject(c1, true);
                                    c1 = null;
                                    created++;
                                }
                                catch { }
                                finally { c1?.Dispose(); if (!consumed) c2?.Dispose(); }
                            }
                        }
                        finally
                        {
                            if (s1l != null) foreach (var s in s1l) s?.Dispose();
                            if (s2l != null) foreach (var s in s2l) s?.Dispose();
                        }
                    }
                    tr.Commit();
                }
                doc.Editor.Regen();
                MessageBox.Show($"{created}개 간섭 솔리드 → '{layerName}' 레이어 생성 완료",
                    "완료", MessageBoxButton.OK, MessageBoxImage.Information);
            }
            catch (Exception ex) { MessageBox.Show($"솔리드 생성 오류: {ex.Message}"); }
        }

        // ── CSV ──────────────────────────────────────────
        private void BtnExportCsv_Click(object sender, RoutedEventArgs e)
        {
            if (_allResults.Count == 0) return;
            var dlg = new Microsoft.Win32.SaveFileDialog
            {
                Filter   = "CSV (*.csv)|*.csv",
                FileName = $"Interference_{DateTime.Now:yyyyMMdd_HHmmss}.csv"
            };
            if (dlg.ShowDialog() != true) return;
            try
            {
                using (var sw = new StreamWriter(dlg.FileName, false, Encoding.UTF8))
                {
                    sw.WriteLine("No,G1_Object,G1_Layer,G2_Object,G2_Layer,Volume,CenterX,CenterY,CenterZ");
                    int n = 1;
                    foreach (var r in _allResults)
                        sw.WriteLine($"{n++},\"{r.Group1Entity.DisplayName}\",{r.Group1Entity.LayerName}," +
                                     $"\"{r.Group2Entity.DisplayName}\",{r.Group2Entity.LayerName}," +
                                     $"{r.InterferenceVolume:F4},{r.InterferenceCenter.X:F3}," +
                                     $"{r.InterferenceCenter.Y:F3},{r.InterferenceCenter.Z:F3}");
                }
                MessageBox.Show($"저장 완료:\n{dlg.FileName}");
            }
            catch (Exception ex) { MessageBox.Show($"오류: {ex.Message}"); }
        }

        // ── 도면 보고서 ──────────────────────────────────
        private void BtnReport_Click(object sender, RoutedEventArgs e)
        {
            if (_allResults.Count == 0) return;
            var doc = AcadApp.DocumentManager.MdiActiveDocument;
            try
            {
                using (doc.LockDocument())
                using (var tr = _db.TransactionManager.StartTransaction())
                {
                    var ms = (BlockTableRecord)tr.GetObject(
                        SymbolUtilityServices.GetBlockModelSpaceId(_db), OpenMode.ForWrite);

                    var sb = new StringBuilder();
                    sb.AppendLine("{\\C1;\\W1;=== 간섭 검사 보고서 ===}");
                    sb.AppendLine($"검사일시: {DateTime.Now:yyyy-MM-dd HH:mm}");
                    sb.AppendLine($"총 간섭 건수: {_allResults.Count}건");
                    foreach (var g in _allResults.GroupBy(r => $"{r.Group1Entity.LayerName} -> {r.Group2Entity.LayerName}").OrderByDescending(g => g.Count()))
                        sb.AppendLine($"  {g.Key}: {g.Count()}건");

                    var mt = new MText { Location = new Point3d(0, -20, 0), TextHeight = 2.5, Width = 200, Contents = sb.ToString() };
                    ms.AppendEntity(mt);
                    tr.AddNewlyCreatedDBObject(mt, true);
                    tr.Commit();
                }
                doc.Editor.Regen();
                MessageBox.Show("도면에 보고서 삽입 완료");
            }
            catch (Exception ex) { MessageBox.Show($"오류: {ex.Message}"); }
        }

        // ── 재검사 ───────────────────────────────────────
        private void BtnRecheck_Click(object sender, RoutedEventArgs e)
        {
            if (_recheckCallback == null) return;

            double minVol;
            if (!double.TryParse(ToleranceBox.Text, out minVol) || minVol < 0) minVol = 0.001;

            StatusText.Text   = "재검사 중... AutoCAD가 잠시 멈춥니다.";
            ProgressBar.Value = 50;
            this.IsEnabled    = false;

            try
            {
                var (results, stats) = _recheckCallback(minVol);
                _allResults = results ?? new List<InterferenceResult>();
                _originalColors.Clear();
                Refresh();
                PopulateStats(stats);
                StatusText.Text   = $"재검사 완료: {_allResults.Count}건";
                ProgressBar.Value = 100;
            }
            catch (Exception ex) { StatusText.Text = $"오류: {ex.Message}"; }
            finally { this.IsEnabled = true; }
        }

        private void BtnCancel_Click(object sender, RoutedEventArgs e) { }

        private void BtnClose_Click(object sender, RoutedEventArgs e)
        {
            if (_originalColors.Count > 0)
            {
                if (MessageBox.Show("변경된 색상을 복원하고 닫으시겠습니까?",
                    "색상 복원", MessageBoxButton.YesNo, MessageBoxImage.Question) == MessageBoxResult.Yes)
                    BtnRestoreColor_Click(null, null);
            }
            Close();
        }

        private void SetButtonsEnabled()
        {
            bool hasResults = _allResults?.Count > 0;
            bool hasSel     = ResultListView.SelectedItems.Count > 0;
            BtnZoom.IsEnabled         = hasSel;
            BtnHighlight.IsEnabled    = hasSel;
            BtnChangeColor.IsEnabled  = hasSel;
            BtnRestoreColor.IsEnabled = _originalColors.Count > 0;
            BtnCreateSolid.IsEnabled  = hasResults;
            BtnExportCsv.IsEnabled    = hasResults;
            BtnReport.IsEnabled       = hasResults;
        }
    }
}
