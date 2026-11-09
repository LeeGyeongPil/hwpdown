# 보안 정책 / Security policy

보안 취약점을 발견하셨다면 **공개 이슈 대신** 이 레포의 **Security → Report a vulnerability**(비공개 취약점 신고)로 알려 주세요. 확인 후 답변드리고, 고친 버전을 릴리스하면서 함께 안내합니다.

If you find a security issue, please **do not open a public issue**. Use **Security → Report a vulnerability** in this repository to report it privately. We will reply after checking and announce the fix with a release.

hwpdown은 서버가 없는 라이브러리이며, 신뢰할 수 없는 문서를 읽을 수 있습니다. 기본 상한(`Limits`: 스트림당 64MiB, 문서 전체 256MiB, 레코드 수·중첩 깊이·표 칸 수)이 적용되어 압축 폭탄을 거부하고, 배포용·암호 문서는 해독하지 않고 거부합니다. / hwpdown is a server-less library that may read untrusted documents. Default `Limits` reject compression bombs, and distribution-protected or encrypted documents are refused, never decrypted.
