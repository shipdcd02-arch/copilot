using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
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
        private readonly List<EntityInfo>       _group1;
        private readonly List<EntityInfo>       _group2;
        private readonly Database               _db;
        private List<InterferenceResult>        _allResults     = new List<InterferenceResult>();
        private ObservableCollection<InterferenceResult> _filtered = new ObservableCollection<InterferenceResult>();
        private CancellationTokenSource         _cts            = new CancellationTokenSource();

        // 색상 복원을 위해 원래 색상 저장
        private Dictionary<ObjectId, int> _originalColors = new Dictionary<ObjectId, int>();

        // ── TreeView 모델 ─────────────────────────────────
        private class TreeNode
        {
            public string       Label       { get; set; }
            public string       CountLabel  { get; set; }
            public List<TreeNode> Children  { get; set; } = new List<TreeNode>();
            public List<InterferenceResult> Results { get; set; }
        }

        // ─────────────────────────────────────────────────
        public InterferenceResultDialog(List<EntityInfo> group1, List<EntityInfo> group2, Database db)
        {
            InitializeComponent();
            _group1 = group1;
            _group2 = group2;
            _db     = db;
            ResultListView.ItemsSource = _filtered;
        }

        // ── 초기화 및 검사 실행 ──────────────────────────
        private async void Window_Loaded(object sender, RoutedEventArgs e)
        {
            await RunCheckAsync(_cts.Token);
        }

        private async Task RunCheckAsync(CancellationToken ct)
        {
            SetButtonsEnabled(false);
            ProgressBar.Value = 0;
            StatusText.Text   = "검사 준비 중...";

            double minVol;
            if (!double.TryParse(ToleranceBox.Text, out minVol) || minVol < 0)
                minVol = 0.001;

            var engine = new InterferenceEngine
            {
                MinVolume     = minVol,
                AabbTolerance = 0.01
            };
            engine.StatusChanged   += msg  => Dispatcher.Invoke(() => StatusText.Text = msg);
            engine.ProgressChanged += (cur, total) => Dispatcher.Invoke(() =>
                ProgressBar.Value = total > 0 ? cur * 100.0 / total : 0);

            List<InterferenceResult> results = null;
            CheckStatistics          stats   = null;

            var doc = AcadApp.DocumentManager.MdiActiveDocument;
            try
            {
                (results, stats) = await Task.Run(() =>
                {
                    using (doc.LockDocument())
                        return engine.CheckInterference(_group1, _group2);
                }, ct);
            }
            catch (OperationCanceledException)
            {
                StatusText.Text = "검사가 취소되었습니다.";
                return;
            }
            catch (Exception ex)
            {
                StatusText.Text = $"오류: {ex.Message}";
                return;
            }

            _allResults = results ?? new List<InterferenceResult>();
            PopulateStats(stats);
            BuildTree();
            ApplyFilter();
            SetButtonsEnabled(true);
            ProgressBar.Value = 100;
        }

        // ── 통계 표시 ────────────────────────────────────
        private void PopulateStats(CheckStatistics s)
        {
            if (s == null) return;
            StatG1.Text     = $"그룹1: {s.TotalGroup1}개";
            StatG2.Text     = $"그룹2: {s.TotalGroup2}개";
            StatPairs.Text  = $"총 쌍: {s.TotalPairs}";
            StatBool.Text   = $"Boolean 연산: {s.BoolOpPerformed}회";
            StatFound.Text  = $"간섭 발견: {s.InterferenceCount}건";
            StatTime.Text   = $"소요: {s.ElapsedSeconds:F1}초";
        }

        // ── 트리 구성 ────────────────────────────────────
        private void BuildTree()
        {
            var root = new List<TreeNode>();
            var byG1Layer = _allResults.GroupBy(r => r.Group1Entity.LayerName);

            foreach (var g1grp in byG1Layer.OrderBy(g => g.Key))
            {
                var g1Node = new TreeNode
                {
                    Label      = $"[G1] {g1grp.Key}",
                    CountLabel = $" ({g1grp.Count()}건)",
                    Results    = g1grp.ToList()
                };
                var byG2 = g1grp.GroupBy(r => r.Group2Entity.LayerName);
                foreach (var g2grp in byG2.OrderBy(g => g.Key))
                {
                    g1Node.Children.Add(new TreeNode
                    {
                        Label      = $"  → [G2] {g2grp.Key}",
                        CountLabel = $" ({g2grp.Count()}건)",
                        Results    = g2grp.ToList()
                    });
                }
                root.Add(g1Node);
            }

            // 전체 노드
            root.Insert(0, new TreeNode
            {
                Label      = "전체",
                CountLabel = $" ({_allResults.Count}건)",
                Results    = _allResults
            });

            SummaryTree.ItemsSource = root;
            if (root.Count > 0)
                ((TreeViewItem)SummaryTree.ItemContainerGenerator.ContainerFromItem(root[0]))
                    ?.ExpandSubtree();
        }

        private void SummaryTree_SelectedItemChanged(object sender, RoutedPropertyChangedEventArgs<object> e)
        {
            if (e.NewValue is TreeNode node)
            {
                _filtered.Clear();
                var filter = FilterBox.Text.Trim().ToLower();
                foreach (var r in node.Results.Where(r => MatchFilter(r, filter)))
                    _filtered.Add(r);
                UpdateListCount();
            }
        }

        // ── 필터 ─────────────────────────────────────────
        private void FilterBox_TextChanged(object sender, TextChangedEventArgs e) => ApplyFilter();

        private void ApplyFilter()
        {
            var filter = FilterBox.Text.Trim().ToLower();
            _filtered.Clear();
            foreach (var r in _allResults.Where(r => MatchFilter(r, filter)))
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

        // ── 리스트 선택 이벤트 ───────────────────────────
        private void ResultListView_SelectionChanged(object sender, SelectionChangedEventArgs e)
        {
            bool any = ResultListView.SelectedItems.Count > 0;
            BtnZoom.IsEnabled        = any;
            BtnHighlight.IsEnabled   = any;
            BtnChangeColor.IsEnabled = any;
        }

        private void ResultListView_DoubleClick(object sender, MouseButtonEventArgs e)
        {
            ZoomToSelected();
        }

        // ── 줌 ───────────────────────────────────────────
        private void BtnZoom_Click(object sender, RoutedEventArgs e) => ZoomToSelected();

        private void ZoomToSelected()
        {
            var selected = ResultListView.SelectedItems.Cast<InterferenceResult>().ToList();
            if (selected.Count == 0) return;

            // 선택된 항목들의 합산 BBox
            var ext = selected.Aggregate(
                selected[0].Group1Entity.BoundingBox,
                (acc, r) =>
                {
                    acc.AddExtents(r.Group1Entity.BoundingBox);
                    acc.AddExtents(r.Group2Entity.BoundingBox);
                    return acc;
                });

            var doc = AcadApp.DocumentManager.MdiActiveDocument;
            try
            {
                using (doc.LockDocument())
                {
                    var ed   = doc.Editor;
                    var view = ed.GetCurrentView();

                    double w = (ext.MaxPoint.X - ext.MinPoint.X) * 1.3;
                    double h = (ext.MaxPoint.Y - ext.MinPoint.Y) * 1.3;
                    w = Math.Max(w, 0.001);
                    h = Math.Max(h, 0.001);
                    double ratio = view.Width / Math.Max(view.Height, 0.001);
                    if (w / h < ratio) w = h * ratio;
                    else               h = w / ratio;

                    view.CenterPoint = new Point2d(
                        (ext.MinPoint.X + ext.MaxPoint.X) / 2,
                        (ext.MinPoint.Y + ext.MaxPoint.Y) / 2);
                    view.Width  = w;
                    view.Height = h;
                    ed.SetCurrentView(view);
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show($"줌 오류: {ex.Message}");
            }
        }

        // ── 간섭 영역 하이라이트 (선택) ──────────────────
        private void BtnHighlight_Click(object sender, RoutedEventArgs e)
        {
            var selected = ResultListView.SelectedItems.Cast<InterferenceResult>().ToList();
            if (selected.Count == 0) return;

            var ids = selected
                .SelectMany(r => new[] { r.Group1Entity.Id, r.Group2Entity.Id })
                .Distinct()
                .ToArray();

            var doc = AcadApp.DocumentManager.MdiActiveDocument;
            try
            {
                using (doc.LockDocument())
                    doc.Editor.SetImpliedSelection(ids);
            }
            catch (Exception ex) { MessageBox.Show($"선택 오류: {ex.Message}"); }
        }

        // ── 색상 변경 ─────────────────────────────────────
        private void BtnChangeColor_Click(object sender, RoutedEventArgs e)
        {
            var selected = ResultListView.SelectedItems.Cast<InterferenceResult>().ToList();
            if (selected.Count == 0) return;

            var ids = selected
                .SelectMany(r => new[] { r.Group1Entity.Id, r.Group2Entity.Id })
                .Distinct().ToList();

            ChangeEntityColors(ids, 1); // 빨간색 (ACI index 1)
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
                    {
                        if (tr.GetObject(kv.Key, OpenMode.ForWrite) is Entity ent)
                            ent.ColorIndex = kv.Value;
                    }
                    tr.Commit();
                }
                doc.Editor.Regen();
                _originalColors.Clear();
                BtnRestoreColor.IsEnabled = false;
            }
            catch (Exception ex) { MessageBox.Show($"색상 복원 오류: {ex.Message}"); }
        }

        private void ChangeEntityColors(List<ObjectId> ids, int colorIdx)
        {
            var doc = AcadApp.DocumentManager.MdiActiveDocument;
            try
            {
                using (doc.LockDocument())
                using (var tr = _db.TransactionManager.StartOpenCloseTransaction())
                {
                    foreach (var id in ids)
                    {
                        if (tr.GetObject(id, OpenMode.ForWrite) is Entity ent)
                        {
                            if (!_originalColors.ContainsKey(id))
                                _originalColors[id] = ent.ColorIndex;
                            ent.ColorIndex = colorIdx;
                        }
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
                    // 레이어 생성 또는 확인
                    var lt = (LayerTable)tr.GetObject(_db.LayerTableId, OpenMode.ForRead);
                    if (!lt.Has(layerName))
                    {
                        lt.UpgradeOpen();
                        var newLayer = new LayerTableRecord { Name = layerName };
                        newLayer.Color = Autodesk.AutoCAD.Colors.Color.FromColorIndex(
                            Autodesk.AutoCAD.Colors.ColorMethod.ByAci, 1);
                        lt.Add(newLayer);
                        tr.AddNewlyCreatedDBObject(newLayer, true);
                    }

                    var ms = (BlockTableRecord)tr.GetObject(
                        SymbolUtilityServices.GetBlockModelSpaceId(_db), OpenMode.ForWrite);

                    foreach (var res in _allResults)
                    {
                        List<Solid3d> s1list = null, s2list = null;
                        try
                        {
                            s1list = res.Group1Entity.GetWorldSolids();
                            s2list = res.Group2Entity.GetWorldSolids();
                            if (s1list == null || s2list == null) continue;

                            foreach (var s1 in s1list)
                            {
                                foreach (var s2 in s2list)
                                {
                                    Solid3d c1 = null, c2 = null;
                                    bool consumed = false;
                                    try
                                    {
                                        c1 = (Solid3d)s1.Clone();
                                        c2 = (Solid3d)s2.Clone();
                                        c1.BooleanOperation(BooleanOperationType.BoolIntersect, c2);
                                        consumed = true;
                                        if (c1.IsNull) { c1.Dispose(); continue; }

                                        c1.Layer      = layerName;
                                        c1.ColorIndex = 1;
                                        ms.AppendEntity(c1);
                                        tr.AddNewlyCreatedDBObject(c1, true);
                                        c1 = null; // 소유권 이전
                                        created++;
                                    }
                                    catch { }
                                    finally
                                    {
                                        c1?.Dispose();
                                        if (!consumed) c2?.Dispose();
                                    }
                                }
                            }
                        }
                        finally
                        {
                            if (s1list != null) foreach (var s in s1list) s?.Dispose();
                            if (s2list != null) foreach (var s in s2list) s?.Dispose();
                        }
                    }
                    tr.Commit();
                }
                doc.Editor.Regen();
                MessageBox.Show($"{created}개의 간섭 솔리드가 '{layerName}' 레이어에 생성되었습니다.",
                    "완료", MessageBoxButton.OK, MessageBoxImage.Information);
            }
            catch (Exception ex)
            {
                MessageBox.Show($"솔리드 생성 오류: {ex.Message}");
            }
        }

        // ── CSV 내보내기 ──────────────────────────────────
        private void BtnExportCsv_Click(object sender, RoutedEventArgs e)
        {
            if (_allResults.Count == 0) return;

            var dlg = new Microsoft.Win32.SaveFileDialog
            {
                Filter   = "CSV 파일 (*.csv)|*.csv",
                FileName = $"InterferenceCheck_{DateTime.Now:yyyyMMdd_HHmmss}.csv"
            };
            if (dlg.ShowDialog() != true) return;

            try
            {
                using (var sw = new StreamWriter(dlg.FileName, false, Encoding.UTF8))
                {
                    sw.WriteLine("No,그룹1 객체,그룹1 레이어,그룹2 객체,그룹2 레이어,간섭 체적,간섭 중심 X,간섭 중심 Y,간섭 중심 Z");
                    int no = 1;
                    foreach (var r in _allResults)
                    {
                        sw.WriteLine(string.Join(",",
                            no++,
                            $"\"{r.Group1Entity.DisplayName}\"",
                            r.Group1Entity.LayerName,
                            $"\"{r.Group2Entity.DisplayName}\"",
                            r.Group2Entity.LayerName,
                            r.InterferenceVolume.ToString("F4"),
                            r.InterferenceCenter.X.ToString("F3"),
                            r.InterferenceCenter.Y.ToString("F3"),
                            r.InterferenceCenter.Z.ToString("F3")));
                    }
                }
                MessageBox.Show($"CSV 파일이 저장되었습니다.\n{dlg.FileName}",
                    "내보내기 완료", MessageBoxButton.OK, MessageBoxImage.Information);
            }
            catch (Exception ex)
            {
                MessageBox.Show($"CSV 저장 오류: {ex.Message}");
            }
        }

        // ── 도면에 보고서 삽입 ────────────────────────────
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

                    // 도면 좌하단 근처에 MText로 보고서 삽입
                    var sb = new StringBuilder();
                    sb.AppendLine("{\\C1;\\W1;=== 간섭 검사 보고서 ===}");
                    sb.AppendLine($"검사일시: {DateTime.Now:yyyy-MM-dd HH:mm:ss}");
                    sb.AppendLine($"총 간섭 건수: {_allResults.Count}건");
                    sb.AppendLine("{\\W0.8;}");

                    var groups = _allResults
                        .GroupBy(r => $"{r.Group1Entity.LayerName} → {r.Group2Entity.LayerName}")
                        .OrderByDescending(g => g.Count());

                    foreach (var g in groups)
                        sb.AppendLine($"  {g.Key}: {g.Count()}건");

                    var mt = new MText
                    {
                        Location   = new Point3d(0, -20, 0),
                        TextHeight = 2.5,
                        Width      = 200,
                        Contents   = sb.ToString()
                    };
                    ms.AppendEntity(mt);
                    tr.AddNewlyCreatedDBObject(mt, true);
                    tr.Commit();
                }
                doc.Editor.Regen();
                MessageBox.Show("도면에 보고서가 삽입되었습니다.", "완료",
                    MessageBoxButton.OK, MessageBoxImage.Information);
            }
            catch (Exception ex)
            {
                MessageBox.Show($"보고서 삽입 오류: {ex.Message}");
            }
        }

        // ── 재검사 ───────────────────────────────────────
        private async void BtnRecheck_Click(object sender, RoutedEventArgs e)
        {
            _cts?.Cancel();
            _cts = new CancellationTokenSource();
            _allResults.Clear();
            _filtered.Clear();
            SummaryTree.ItemsSource = null;
            _originalColors.Clear();
            await RunCheckAsync(_cts.Token);
        }

        private void BtnCancel_Click(object sender, RoutedEventArgs e)
        {
            _cts?.Cancel();
            StatusText.Text = "취소 중...";
        }

        private void BtnClose_Click(object sender, RoutedEventArgs e)
        {
            _cts?.Cancel();
            // 색상이 변경된 채로 닫힌 경우 사용자에게 알림
            if (_originalColors.Count > 0)
            {
                var r = MessageBox.Show("변경된 색상을 복원하고 닫으시겠습니까?",
                    "색상 복원", MessageBoxButton.YesNo, MessageBoxImage.Question);
                if (r == MessageBoxResult.Yes)
                    BtnRestoreColor_Click(null, null);
            }
            Close();
        }

        private void SetButtonsEnabled(bool on)
        {
            BtnZoom.IsEnabled         = false; // 선택 시에만 활성화
            BtnHighlight.IsEnabled    = false;
            BtnChangeColor.IsEnabled  = false;
            BtnCreateSolid.IsEnabled  = on && _allResults?.Count > 0;
            BtnExportCsv.IsEnabled    = on && _allResults?.Count > 0;
            BtnReport.IsEnabled       = on && _allResults?.Count > 0;
        }
    }
}
