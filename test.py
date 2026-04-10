# 레이어 생성 시 색상까지 같이 설정
if use_layer:
    lines += ["-LAYER", "M", layer_name, ""]
    if has_color:
        if solid_color_aci is not None:
            lines += ["-LAYER", "C", str(solid_color_aci), layer_name, ""]
        elif solid_color_rgb is not None:
            r, g, b = solid_color_rgb
            lines += ["-LAYER", "C", "T", f"{r},{g},{b}", layer_name, ""]

lines.append(f'_ACISIN "{sat_path}"')

# 레이어 이동만 (색상은 레이어에 설정했으므로 개체 색상 변경 불필요)
if use_layer:
    lines += ["_CHPROP", "_all", "", "LA", layer_name, ""]
elif has_color and not use_layer:
    # 레이어 없이 색상만 적용하는 경우는 기존 방식 유지
    lines += ["_CHPROP", "_all", ""] + _color_args() + [""]


# 저장 전 현재 레이어를 0으로 복원
lines += ["CLAYER", "0"]
lines += ["_SAVEAS", dwg_version, f'"{dwg_path}"', "_QUIT Y", ""]
