# blog-keyword

네이버 검색광고 API로 맛집 블로그 키워드를 매일 자동 추천하는 도구입니다.

- 매일 GitHub Actions가 `blog_keyword.py`를 실행합니다.
- 결과 CSV는 `results/`, 대시보드는 `docs/index.html` (GitHub Pages)로 저장됩니다.
- API 키는 저장소 Settings > Secrets and variables > Actions 에만 보관합니다. 코드나 파일에 키를 넣지 마세요.
- 씨앗 키워드는 `seeds.txt`에서 수정합니다.
