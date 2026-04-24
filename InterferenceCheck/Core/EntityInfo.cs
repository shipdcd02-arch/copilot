using System;
using System.Collections.Generic;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Geometry;

namespace InterferenceCheck.Core
{
    /// <summary>
    /// ModelSpace 내 검사 대상 엔티티 (Solid3d 또는 BlockReference) 정보
    /// </summary>
    public class EntityInfo
    {
        /// <summary>ModelSpace 상의 원본 ObjectId (줌/선택에 사용)</summary>
        public ObjectId Id { get; set; }

        /// <summary>결과 창에 표시할 이름</summary>
        public string DisplayName { get; set; }

        public string LayerName { get; set; }

        /// <summary>월드 좌표계 기준 외접 박스</summary>
        public Extents3d BoundingBox { get; set; }

        public bool IsBlockReference { get; set; }
        public string BlockName { get; set; }

        /// <summary>
        /// 월드 좌표계로 변환된 Solid3d 복사본 목록을 반환하는 팩토리.
        /// 호출자가 각 Solid3d를 Dispose 해야 함.
        /// </summary>
        public Func<List<Solid3d>> GetWorldSolids { get; set; }
    }
}
