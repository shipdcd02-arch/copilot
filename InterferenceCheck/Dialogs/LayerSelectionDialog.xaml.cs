using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using InterferenceCheck.Models;

namespace InterferenceCheck.Dialogs
{
    public partial class LayerSelectionDialog : Window
    {
        private readonly ObservableCollection<LayerItem> _all;
        public List<string> SelectedLayers { get; private set; } = new List<string>();

        public LayerSelectionDialog(IEnumerable<string> layers, string title)
        {
            InitializeComponent();
            TitleText.Text = title;
            _all = new ObservableCollection<LayerItem>(layers.Select(l => new LayerItem { Name = l }));
            LayerListBox.ItemsSource = _all;
            UpdateCount();
        }

        private void SearchBox_TextChanged(object sender, TextChangedEventArgs e)
        {
            var filter = SearchBox.Text.Trim().ToLower();
            LayerListBox.ItemsSource = string.IsNullOrEmpty(filter)
                ? _all
                : new ObservableCollection<LayerItem>(_all.Where(i => i.Name.ToLower().Contains(filter)));
        }

        private void Check_Changed(object sender, RoutedEventArgs e) => UpdateCount();

        private void SelectAll_Click(object sender,  RoutedEventArgs e) { foreach (var i in _all) i.IsSelected = true;  UpdateCount(); }
        private void SelectNone_Click(object sender, RoutedEventArgs e) { foreach (var i in _all) i.IsSelected = false; UpdateCount(); }

        private void UpdateCount() =>
            CountLabel.Text = $"{_all.Count(i => i.IsSelected)}개 선택됨";

        private void OK_Click(object sender, RoutedEventArgs e)
        {
            SelectedLayers = _all.Where(i => i.IsSelected).Select(i => i.Name).ToList();
            if (SelectedLayers.Count == 0)
            {
                MessageBox.Show("레이어를 하나 이상 선택하세요.", "알림",
                    MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }
            DialogResult = true;
        }

        private void Cancel_Click(object sender, RoutedEventArgs e) => DialogResult = false;
    }
}
