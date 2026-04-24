using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Geometry;
using InterferenceCheck.Core;

namespace InterferenceCheck.Models
{
    public class InterferenceResult
    {
        public EntityInfo Group1Entity  { get; set; }
        public EntityInfo Group2Entity  { get; set; }
        public double     InterferenceVolume   { get; set; }
        public Point3d    InterferenceCenter   { get; set; }
        public Extents3d  InterferenceExtents  { get; set; }

        public string VolumeText  => $"{InterferenceVolume:F4}";
        public string CenterText  => $"({InterferenceCenter.X:F1}, {InterferenceCenter.Y:F1}, {InterferenceCenter.Z:F1})";
    }

    public class CheckStatistics
    {
        public int      TotalGroup1         { get; set; }
        public int      TotalGroup2         { get; set; }
        public int      TotalPairs          { get; set; }
        public int      AabbCandidates      { get; set; }
        public int      SphereCandidates    { get; set; }
        public int      BoolOpPerformed     { get; set; }
        public int      InterferenceCount   { get; set; }
        public double   ElapsedSeconds      { get; set; }
    }
}
