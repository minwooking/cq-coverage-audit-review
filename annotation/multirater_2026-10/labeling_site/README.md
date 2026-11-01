# 역량 질문 라벨링 사이트 (블라인드 다중 평가자용)

- 게시 위치: claude.ai 아티팩트 (조직 공유, 평가자는 '기여자' 권한 필요)
- `index.html`: 사이트 전체(단일 파일). `data/cells.json`(188셀: 질문·범주·참고 번역·시작점 용어, 판정 모델 점수·변형 이름 없음), `data/views_manifest.json`(렌더링 텍스트 6개의 SHA-256).
- 렌더링 텍스트 파일(`views/v-*.txt`, 약 12MB)은 게시하지 않는다. 평가자에게 `../views_for_raters.zip`(git 미추적)으로 따로 배포하고, 브라우저 IndexedDB에만 보관한다.
- 그래프 탭은 텍스트 자료를 브라우저에서 파싱해 만든다(별도 그래프 파일 없음). 노드를 누르면 원문 정의 줄로 이동한다. 철자 자동 교정 포함.
- 텍스트 보기 필터: 전체 줄 / 검색어가 강조된 줄만 / 그래프에 나온 노드의 정의 줄만(원래 줄 번호와 원문 그대로 유지).
- 권한: 평가자는 '기여자' 이상(편집자 가능). '보기' 권한은 플랫폼 규칙상 저장 불가라, 페이지가 처음에 권한을 확인해 안내 화면을 띄운다.
- 작업 나누기(관리 탭, 기본 켜짐·셀당 2명): 셀당 목표 인원(1·2·3명)이 평가를 마친 셀은 다른 평가자에게 나오지 않는다. 완료 표시 id는 "<셀>__<평가자>". 완료 표시만 `done/<cellId>`에 공유하고 라벨 내용은 공유하지 않는다. 켜면 셀당 평가자가 한 명이라 평가자 간 일치도는 계산할 수 없다.
- 문항 검토 탭(소유자 전용): 확장 은행 84문항(addendum 20)을 승인·수정 승인·제외로 검토. 문항은 db `cqreview/<cq_id>`에 있고 소유자만 읽고 쓴다(편집자·기여자에게 보이지 않음).
- db 규칙: labels(소유자만 읽기·쓰기), cqreview(소유자만), labels/{self}(기여자 이상 본인 것), done(기여자 이상 읽기·쓰기), config(누구나 읽기, 소유자만 쓰기).
- 저장소: 아티팩트 db `labels/<uid>/items/<cellId>` (S, R, span, note, 체류 시간, 검색·그래프 질의 기록, 수정 이력).
- 변형 키(`site_key_2026-10-13.csv`)는 git에 넣지 않는다.
- AI가 생성한 코드이므로 배포 전에 사람이 검토·시험한다.

## Note added in this package: external resources loaded by `index.html`

The page is released as it was used. When it is opened it requests resources from three third-party hosts: the web fonts
JetBrains Mono and Noto Sans KR from Google Fonts (`fonts.googleapis.com`, `fonts.gstatic.com`) and the Cytoscape.js 3.30.2 graph
library from cdnjs (`cdnjs.cloudflare.com`). Opening the page therefore sends the viewer's IP address and browser identification
to those hosts. Without network access the fonts fall back to browser defaults and the graph tab, which needs Cytoscape.js,
shows a load-failure message (the text tab keeps working). To use the page offline, download those files, serve them from the page's own folder and change the font and
script URLs in `index.html`. (AI-generated page; review and test it before any reuse.)
