# Maya VAT Encoder
[![Maya](https://img.shields.io/badge/Maya-2022+-00B4FF?style=flat-square&logo=autodesk)](https://www.autodesk.com/products/maya)
[![Python](https://img.shields.io/badge/Python-Pure-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)
[![Version](https://img.shields.io/badge/Version-1.1.0-blue?style=flat-square)]()

🌐 [English](README.md) | 한국어 · 🔗 **[프로젝트 페이지](https://5hyuns.github.io/Maya-Vertex-Animation-Texture-Baker/)** · ⬇️ **[다운로드](https://github.com/5hyuns/Maya-Vertex-Animation-Texture-Baker/releases/latest)**

**Maya용 Vertex Animation Texture 인코더** - 스킨메시, 디포머 등 움직이는 모든 것을 VAT로 변환해보세요!

**Houdini 없이 Maya 안에서** 스켈레탈(skinCluster)·블렌드쉐입·디포머 애니메이션을 **버텍스 애니메이션 텍스처(VAT)** 로 굽는 무료 오픈소스 툴입니다. Position/Normal 텍스처, 바운드 JSON, 프록시 FBX를 출력하며, 버텍스 셰이더로 언리얼 엔진·유니티·PlayCanvas·three.js(WebGL) 등에서 재생할 수 있습니다. 군중(crowd)이나 대량 인스턴스 애니메이션에 적합합니다.

![Demo](https://github.com/user-attachments/assets/e7b50f13-9a43-4ebe-9f14-aee65729311b)
<sub>*Astro Bot*™ © Sony Interactive Entertainment. Unofficial fan remake.</sub>

## 목차

- [특징](#특징)
- [설치](#설치)
- [빠른 시작](#빠른-시작)
- [옵션](#옵션)
- [출력 파일](#출력-파일)
- [출력 예시](#출력-예시)
- [텍스처 포맷](#텍스처-포맷)
- [엔진에서 재생하기](#엔진에서-재생하기)
- [Python API](#python-api)
- [주의사항](#주의사항)

---

## 특징

- **의존성 없음** - 순수 Python, 추가 설치 불필요
- **Object/World Space** - 용도에 맞는 좌표계 선택
- **자동 VAT UV 생성** - 버텍스 ID 기반 UV 자동 할당
- **Skip First Frame** - T-Pose 제외 옵션
- **원클릭 출력** - PNG + JSON + FBX 일괄 생성

---

## 설치

1. [최신 릴리스](https://github.com/5hyuns/Maya-Vertex-Animation-Texture-Baker/releases/latest)(또는 *Code > Download ZIP*)를 받아 압축을 풉니다.
2. 압축 푼 폴더(예: `Maya-Vertex-Animation-Texture-Baker-main`)의 이름을 **`maya_vat`** 으로 바꿉니다. 폴더 이름이 곧 파이썬 패키지 이름입니다.
3. `maya_vat` 폴더를 Maya 스크립트 경로에 복사합니다.
   ```
   # Windows
   C:/Users/<사용자>/Documents/maya/<버전>/scripts/

   # macOS
   ~/Library/Preferences/Autodesk/maya/<버전>/scripts/

   # Linux
   ~/maya/<버전>/scripts/
   ```
4. Maya를 재시작한 뒤 Script Editor에서 아래 빠른 시작 코드를 실행합니다.

**요구 사항:** Maya 2022 이상 (PySide2 / PySide6). FBX 플러그인(`fbxmaya`)은 메시를 내보낼 때만 필요합니다.

---

## 빠른 시작

```python
import maya_vat
maya_vat.show()
```

1. 애니메이션된 메시를 선택하고 **Target Mesh** 옆 `<<` 버튼을 누릅니다.
2. **Frame Range**(`Timeline` 버튼으로 타임라인 범위 입력), **Coordinate Space**, 옵션을 설정합니다.
3. **Output Directory**를 지정하고 **Encode VAT**를 누릅니다.

---

## 옵션

![UI](https://github.com/user-attachments/assets/dd124ec8-42ee-4941-a186-06b7c061b25c)

### Coordinate Space

| 옵션 | 사용 상황 |
|------|-----------|
| **Object (Local)** | 런타임에 캐릭터 이동/회전 필요 **(권장)** |
| **World** | Transform 고정 (배경 오브젝트 등) |

### Skip First Frame

| 상황 | 설정 |
|------|------|
| 첫 프레임이 T-Pose/Bind Pose | **ON** |
| 첫 프레임부터 애니메이션 시작 | **OFF** |

ON이면 첫 프레임은 프록시(기준) 포즈로만 쓰이고 텍스처에는 들어가지 않습니다. 그래서 텍스처 행이 하나 줄어듭니다.

### 기타 옵션

| 옵션 | 설명 |
|------|------|
| **Export Normals (separate texture)** | `<mesh>_vnrm.png`도 함께 출력 |
| **Export Mesh (FBX)** | 첫 프레임 포즈의 프록시 메시 출력 |
| **UV Set Name** / **Overwrite if exists** | 생성할 VAT UV 세트 이름. Overwrite를 켜면 기존 세트를 지우고 다시 만듭니다. **Create VAT UV**는 UV 세트만 만듭니다. |

---

## 출력 파일

```
output_dir/
+-- <mesh>_vat/
    +-- <mesh>_vat.png       # Position 델타 텍스처
    +-- <mesh>_vnrm.png      # Normal 텍스처 (선택)
    +-- <mesh>_remap.json    # 디코딩용 min/max 바운드
    +-- <mesh>.fbx           # 프록시 메시 (선택)
```

메시 이름의 `:`와 `|`는 `_`로 바뀝니다.

---

## 출력 예시

위 데모의 Astro Bot 메시에서 실제로 구워낸 텍스처입니다. **버텍스 2253개 × 524 프레임**이라 텍스처 크기는 2253 × 524 px입니다 (아래 이미지는 가로 1024 px로 줄인 미리보기).

**Position 텍스처** (`_vat.png`)

![Position 텍스처 예시](docs/assets/example_vat.png)

**Normal 텍스처** (`_vnrm.png`)

![Normal 텍스처 예시](docs/assets/example_vnrm.png)

보는 법:

- **세로 한 줄 = 버텍스 하나** (열 x = 버텍스 ID), **가로 한 줄 = 프레임 하나** (맨 위가 첫 프레임)입니다.
- **Position 텍스처:** 각 픽셀은 프록시 포즈에서 해당 버텍스가 이동한 XYZ 값을 JSON의 min/max로 RGB에 매핑한 것입니다. 색이 고르고 잔잔한 영역은 거의 움직이지 않는 버텍스이고, 채도가 강한 세로 띠는 팔·다리처럼 많이 움직이는 부위입니다. 가로 띠는 몸 전체가 함께 움직인 프레임입니다.
- **Normal 텍스처:** 각 픽셀은 버텍스 노멀을 -1..1에서 0..255로 매핑한 값입니다. 표면 방향에 따라 색이 달라서 Position보다 훨씬 다채롭게 보입니다.
- 버텍스 ID는 보통 모델링 순서를 따르기 때문에, 이웃한 열은 같은 부위인 경우가 많아 비슷한 패턴을 보입니다.

---

## 텍스처 포맷

```
Width  = 버텍스 수
Height = 프레임 수

        V0    V1    V2    V3   ...   Vn
      +-----+-----+-----+-----+---+-----+
  F0  | RGB | RGB | RGB | RGB |...| RGB |  <- Row 0
  F1  | RGB | RGB | RGB | RGB |...| RGB |  <- Row 1
  F2  | RGB | RGB | RGB | RGB |...| RGB |  <- Row 2
   :  |     |     |     |     |   |     |
      +-----+-----+-----+-----+---+-----+

픽셀 RGB = (deltaX, deltaY, deltaZ) normalized to 0-255
```

| 항목 | 값 |
|------|-----|
| 포맷 | 8-bit RGB PNG |
| Position | `delta = position(frame) - position(proxy)`, 축별로 전체 공통 min/max 하나로 리맵 |
| Normal | -1..1 → 0..255, **X축 반전** (PlayCanvas 호환) |
| VAT UV | `U = (vertex_id + 0.5) / vertex_count`, `V` = 첫 행의 중앙 |
| 프록시 | 프레임 범위 첫 프레임의 메시 포즈 |

### `<mesh>_remap.json`

```json
{
    "position": {
        "min": [-2.5, -1.0, -0.5],
        "max": [3.2, 4.5, 1.2],
        "frames": 60,
        "vertices": 1024,
        "space": "object"
    },
    "normal": {
        "min": [-1, -1, -1],
        "max": [1, 1, 1]
    }
}
```

`normal`은 노멀을 출력했을 때만 들어갑니다.

---

## 엔진에서 재생하기

버텍스 셰이더에서 `VAT_UV` 세트로 텍스처를 샘플링한 뒤, 디코딩한 오프셋을 프록시 위치에 더합니다.

```hlsl
// vatUV        : 버텍스의 VAT_UV
// frame        : 현재 프레임, 0 .. frames-1
// boundsMin/Max: remap.json의 position.min / position.max
float2 uv     = float2(vatUV.x, (frame + 0.5) / frames);
float3 enc    = tex2Dlod(_VatPosition, float4(uv, 0, 0)).rgb;
float3 offset = lerp(boundsMin, boundsMax, enc);
float3 posOS  = proxyPositionOS + offset;

float3 n = tex2Dlod(_VatNormal, float4(uv, 0, 0)).rgb * 2 - 1;
n.x = -n.x;   // X 반전 되돌리기 (엔진이 PlayCanvas 규칙을 따르면 생략)
```

텍스처 임포트 설정:

- 필터링은 **Point / Nearest**, **밉맵 끔**
- **Linear** (sRGB 끔), **압축 없음**
- 엔진이 텍스처를 V 반전 상태로 읽는다면 V를 뒤집어 주세요 (예: `1 - v`).

8-bit 정밀도는 축별로 `(max - min) / 255`입니다. 움직임 범위가 클수록 단계가 거칠어집니다.

---

## Python API

### VAT 인코딩

```python
from maya_vat import core, utils

result = core.encode_vat(
    mesh_name="pCube1",
    output_dir="C:/output",
    frame_start=0,
    frame_end=60,
    include_normals=True,
    export_mesh=True,
    use_world_space=False,      # Object Space 권장
    uv_set_name="VAT_UV",
    force_uv=False,
    skip_first_frame=True       # T-Pose 제외
)

# 반환값
# {
#     "success": True,
#     "png_path": "C:/output/pCube1_vat/pCube1_vat.png",
#     "json_path": "C:/output/pCube1_vat/pCube1_remap.json",
#     "fbx_path": "C:/output/pCube1_vat/pCube1.fbx",
#     "width": 8,
#     "height": 60,
#     ...
# }
```

### VAT UV 독립 생성

```python
uv_result = utils.create_vat_uv(
    mesh_name="pCube1",
    num_verts=1024,
    num_frames=60,
    uv_set_name="VAT_UV",
    force=False  # 존재하면 스킵
)

# UV 세트 존재 확인
exists = utils.uv_set_exists("pCube1", "VAT_UV")
```

### 패키지 구조

```
maya_vat/
+-- __init__.py      # 패키지 진입점 (show, encode_vat)
+-- core.py          # VAT 인코딩 로직, PNG 저장
+-- utils.py         # Maya API 유틸리티, VAT UV 생성
+-- exporter.py      # FBX/OBJ 내보내기
+-- ui.py            # PySide2/6 UI
```

---

## 주의사항

### Object Space vs World Space

| 상황 | Object | World |
|------|:------:|:-----:|
| 런타임 이동/회전 | O | X |
| 루트 모션 애니메이션 | O | X (중복 이동) |
| Transform 고정 | O | O |

### UV 세트

- 기존 UV 세트와 이름이 겹치지 않게 주의하세요.
- `Overwrite if exists`를 체크하면 기존 UV 세트를 지우고 다시 만듭니다.
- UV Editor > UV Sets에서 확인할 수 있습니다.

### FBX 내보내기

- 스킨/본 제외 (VAT는 스킨 불필요)
- 블렌드쉐입 제외
- 애니메이션 제외 (첫 프레임만)

### 제한 사항

- 프레임 범위 전체에서 버텍스 수와 순서가 같아야 합니다 (토폴로지가 바뀌는 애니메이션은 지원하지 않음).
- 텍스처 가로 크기 = 버텍스 수입니다. 하이폴리 메시라면 대상 엔진의 최대 텍스처 크기를 확인하세요.

---

## License

[MIT License](LICENSE)

---

**Contact:** 555hyuns@gmail.com
