using System;
using System.Collections.Generic;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Geometry;
using InterferenceCheck.Models;

namespace InterferenceCheck.Core
{
    /// <summary>
    /// 3단계 필터링 후 Boolean 교차로 간섭을 확인한다.
    ///   1단계: AABB (축 정렬 경계 박스) 중첩
    ///   2단계: 경계 구(Bounding Sphere) 중첩
    ///   3단계: 솔리드 레벨 AABB → BooleanIntersect → 체적 임계값
    /// </summary>
    public class InterferenceEngine
    {
        // ── 설정 ──────────────────────────────────────────
        /// <summary>간섭으로 인정할 최소 체적 (기본 0.001 drawing unit³)</summary>
        public double MinVolume    { get; set; } = 0.001;
        /// <summary>AABB 팽창 여유 (단위 길이)</summary>
        public double AabbTolerance { get; set; } = 0.01;

        // ── 이벤트 ────────────────────────────────────────
        public event Action<string>  StatusChanged;
        public event Action<int,int> ProgressChanged;
        public bool IsCancelled { get; set; }

        // ─────────────────────────────────────────────────
        // 메인 진입점
        // ─────────────────────────────────────────────────
        public (List<InterferenceResult> results, CheckStatistics stats)
            CheckInterference(List<EntityInfo> group1, List<EntityInfo> group2)
        {
            var results = new List<InterferenceResult>();
            var stats   = new CheckStatistics
            {
                TotalGroup1 = group1.Count,
                TotalGroup2 = group2.Count,
                TotalPairs  = group1.Count * group2.Count
            };

            var sw = System.Diagnostics.Stopwatch.StartNew();
            Report($"총 {group1.Count} × {group2.Count} = {stats.TotalPairs} 쌍 검사 시작");

            // ── 1단계: AABB ──────────────────────────────
            var aabbPass = new List<(EntityInfo, EntityInfo)>();
            int idx = 0;
            foreach (var e1 in group1)
            {
                foreach (var e2 in group2)
                {
                    if (IsCancelled) goto Done;
                    if (AabbOverlap(e1.BoundingBox, e2.BoundingBox, AabbTolerance))
                        aabbPass.Add((e1, e2));
                    ProgressChanged?.Invoke(++idx, stats.TotalPairs);
                }
            }
            stats.AabbCandidates = aabbPass.Count;
            Report($"1단계 AABB 통과: {aabbPass.Count}쌍");

            // ── 2단계: Bounding Sphere ───────────────────
            var spherePass = new List<(EntityInfo, EntityInfo)>();
            foreach (var (e1, e2) in aabbPass)
            {
                if (SphereOverlap(e1.BoundingBox, e2.BoundingBox, AabbTolerance))
                    spherePass.Add((e1, e2));
            }
            stats.SphereCandidates = spherePass.Count;
            Report($"2단계 구(Sphere) 통과: {spherePass.Count}쌍 → Boolean 연산 시작");

            // ── 3단계: Boolean Intersect ─────────────────
            int bIdx = 0;
            foreach (var (e1, e2) in spherePass)
            {
                if (IsCancelled) goto Done;
                stats.BoolOpPerformed++;
                var res = BooleanCheck(e1, e2);
                if (res != null) results.Add(res);
                ProgressChanged?.Invoke(++bIdx, spherePass.Count);
                Report($"Boolean 연산 {bIdx}/{spherePass.Count} (발견: {results.Count}건)");
            }

        Done:
            sw.Stop();
            stats.InterferenceCount = results.Count;
            stats.ElapsedSeconds    = sw.Elapsed.TotalSeconds;
            Report($"검사 완료 — {results.Count}건 발견 / {sw.Elapsed.TotalSeconds:F1}초 소요");
            return (results, stats);
        }

        // ─────────────────────────────────────────────────
        // 기하 필터
        // ─────────────────────────────────────────────────
        private bool AabbOverlap(Extents3d a, Extents3d b, double tol)
        {
            return a.MinPoint.X - tol <= b.MaxPoint.X && a.MaxPoint.X + tol >= b.MinPoint.X
                && a.MinPoint.Y - tol <= b.MaxPoint.Y && a.MaxPoint.Y + tol >= b.MinPoint.Y
                && a.MinPoint.Z - tol <= b.MaxPoint.Z && a.MaxPoint.Z + tol >= b.MinPoint.Z;
        }

        private static Point3d Center(Extents3d e) =>
            new Point3d((e.MinPoint.X + e.MaxPoint.X) / 2,
                        (e.MinPoint.Y + e.MaxPoint.Y) / 2,
                        (e.MinPoint.Z + e.MaxPoint.Z) / 2);

        private static double Radius(Extents3d e) =>
            Center(e).DistanceTo(e.MaxPoint);

        private bool SphereOverlap(Extents3d a, Extents3d b, double tol) =>
            Center(a).DistanceTo(Center(b)) <= Radius(a) + Radius(b) + tol;

        // ─────────────────────────────────────────────────
        // Boolean 교차 검사 (솔리드 레벨 분해 처리)
        // ─────────────────────────────────────────────────
        private InterferenceResult BooleanCheck(EntityInfo e1, EntityInfo e2)
        {
            List<Solid3d> s1list = null, s2list = null;
            try
            {
                s1list = e1.GetWorldSolids();
                s2list = e2.GetWorldSolids();
                if (s1list == null || s1list.Count == 0) return null;
                if (s2list == null || s2list.Count == 0) return null;

                double      totalVol = 0;
                Extents3d?  intExt   = null;

                foreach (var s1 in s1list)
                {
                    foreach (var s2 in s2list)
                    {
                        // 솔리드 레벨 AABB 추가 확인
                        Extents3d ext1, ext2;
                        try { ext1 = s1.GeometricExtents; ext2 = s2.GeometricExtents; }
                        catch { continue; }
                        if (!AabbOverlap(ext1, ext2, AabbTolerance * 0.1)) continue;

                        var vol = TryBoolIntersect(s1, s2, out Extents3d resExt);
                        if (vol > MinVolume)
                        {
                            totalVol += vol;
                            intExt = intExt == null ? resExt : UnionExtents(intExt.Value, resExt);
                        }
                    }
                }

                if (totalVol <= MinVolume || intExt == null) return null;

                var c = Center(intExt.Value);
                return new InterferenceResult
                {
                    Group1Entity        = e1,
                    Group2Entity        = e2,
                    InterferenceVolume  = totalVol,
                    InterferenceCenter  = c,
                    InterferenceExtents = intExt.Value
                };
            }
            catch { return null; }
            finally
            {
                if (s1list != null) foreach (var s in s1list) s?.Dispose();
                if (s2list != null) foreach (var s in s2list) s?.Dispose();
            }
        }

        /// <summary>
        /// s1, s2 클론으로 BoolIntersect를 시도한다.
        /// copy2는 성공 시 AutoCAD가 소비(consume)하므로 별도 Dispose 불필요.
        /// 예외 시에는 copy2를 직접 Dispose한다.
        /// </summary>
        private double TryBoolIntersect(Solid3d s1, Solid3d s2, out Extents3d resultExt)
        {
            resultExt = default;
            Solid3d copy1 = null, copy2 = null;
            bool consumed = false;
            try
            {
                copy1 = (Solid3d)s1.Clone();
                copy2 = (Solid3d)s2.Clone();
                copy1.BooleanOperation(BooleanOperationType.BoolIntersect, copy2);
                consumed = true; // copy2는 이제 무효

                if (copy1.IsNull) return 0;

                double vol = copy1.MassProperties.Volume;
                if (vol > MinVolume)
                {
                    try { resultExt = copy1.GeometricExtents; }
                    catch { /* 극히 얇은 솔리드 */ }
                }
                return vol;
            }
            catch
            {
                return 0;
            }
            finally
            {
                copy1?.Dispose();
                if (!consumed) copy2?.Dispose();
            }
        }

        private static Extents3d UnionExtents(Extents3d a, Extents3d b) =>
            new Extents3d(
                new Point3d(Math.Min(a.MinPoint.X, b.MinPoint.X),
                            Math.Min(a.MinPoint.Y, b.MinPoint.Y),
                            Math.Min(a.MinPoint.Z, b.MinPoint.Z)),
                new Point3d(Math.Max(a.MaxPoint.X, b.MaxPoint.X),
                            Math.Max(a.MaxPoint.Y, b.MaxPoint.Y),
                            Math.Max(a.MaxPoint.Z, b.MaxPoint.Z)));

        private void Report(string msg) => StatusChanged?.Invoke(msg);
    }
}
