"""seed_data_large.py: 대규모 시드 데이터 생성 스크립트.

5만 사용자, 25만 게시글, 75만 댓글 등 대규모 데이터를 생성하여
추천 피드, 검색, 페이지네이션 등의 성능을 검증합니다.

사용법:
    source .venv/bin/activate

    # SSH 터널 경유 RDS 시딩
    python core/database/seed_data_large.py --db-user admin --db-password SECRET --dry-run

    # 로컬 MySQL 시딩
    python core/database/seed_data_large.py --db-host 127.0.0.1 --db-port 3306 \\
        --db-user root --db-password root --no-confirm

사용자 티어:
    - Power (5%): 게시글/댓글 다수 생성
    - Regular (25%): 일반적 활동
    - Reader (70%): 주로 조회/좋아요만
"""

import argparse
import asyncio
import math
import random
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

# 프로젝트 루트를 PYTHONPATH에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

import aiomysql
from faker import Faker

from core.utils.password import hash_password

fake = Faker("ko_KR")
Faker.seed(42)  # 재현 가능한 데이터
random.seed(42)

# ─────────────────────────────────────────────
# 태그 상수
# ─────────────────────────────────────────────

TAG_NAMES = [
    # 인기 태그 (상위 10개 — post_tag의 50% 차지)
    "ubuntu",
    "arch",
    "fedora",
    "debian",
    "docker",
    "kernel",
    "systemd",
    "vim",
    "bash",
    "ssh",
    # 중간 인기 (11~25)
    "wayland",
    "gnome",
    "kde",
    "i3wm",
    "nginx",
    "neovim",
    "zsh",
    "dotfiles",
    "xorg",
    "mint",
    "git",
    "tmux",
    "서버관리",
    "보안",
    "네트워크",
    # 일반 (26~50)
    "파일시스템",
    "패키지관리",
    "가상화",
    "백업",
    "모니터링",
    "성능최적화",
    "apache",
    "cron",
    "firewall",
    "grub",
    "btrfs",
    "zfs",
    "ansible",
    "terraform",
    "kubernetes",
    "python",
    "rust",
    "go",
    "flatpak",
    "snap",
    "opensuse",
    "manjaro",
    "rocky",
    "alpine",
    "proxmox",
]

# 미리 해시된 비밀번호 (Test1234!)
HASHED_PASSWORD = hash_password("Test1234!")

# 배포판 분포 (Camp Linux 테마)
DISTROS = ["ubuntu", "fedora", "arch", "debian", "mint", "opensuse", "manjaro", "other", None]
DISTRO_WEIGHTS = [0.30, 0.15, 0.15, 0.12, 0.08, 0.05, 0.05, 0.05, 0.05]

# ─────────────────────────────────────────────
# 사용자 티어 상수
# ─────────────────────────────────────────────

TOTAL_USERS = 50_000
POWER_RATIO = 0.05  # 2,500명 — 게시글/댓글 다수 생성
REGULAR_RATIO = 0.25  # 12,500명 — 일반적 활동
READER_RATIO = 0.70  # 35,000명 — 주로 조회/좋아요

POWER_COUNT = int(TOTAL_USERS * POWER_RATIO)  # 2,500
REGULAR_COUNT = int(TOTAL_USERS * REGULAR_RATIO)  # 12,500
READER_COUNT = TOTAL_USERS - POWER_COUNT - REGULAR_COUNT  # 35,000

# 1-indexed ID 범위
POWER_IDS = range(1, POWER_COUNT + 1)  # 1 ~ 2,500
REGULAR_IDS = range(POWER_COUNT + 1, POWER_COUNT + REGULAR_COUNT + 1)  # 2,501 ~ 15,000
READER_IDS = range(POWER_COUNT + REGULAR_COUNT + 1, TOTAL_USERS + 1)  # 15,001 ~ 50,000

# 배치 크기
BATCH_SIZE = 5_000


# ─────────────────────────────────────────────
# DB 연결
# ─────────────────────────────────────────────


async def create_pool(args) -> aiomysql.Pool:
    """CLI 인자로부터 aiomysql 커넥션 풀 생성.

    SSH 터널 경유 시 커넥션 수를 적게 유지 (minsize=5, maxsize=10).
    """
    print(f"DB 연결: {args.db_user}@{args.db_host}:{args.db_port}/{args.db_name}")
    pool = await aiomysql.create_pool(
        host=args.db_host,
        port=args.db_port,
        user=args.db_user,
        password=args.db_password,
        db=args.db_name,
        minsize=5,
        maxsize=10,
        connect_timeout=10,
        charset="utf8mb4",
        autocommit=True,
    )
    print("  커넥션 풀 생성 완료 (min=5, max=10)")
    return pool


# ─────────────────────────────────────────────
# 고성능 배치 INSERT 헬퍼
# ─────────────────────────────────────────────


async def batch_insert_raw(
    pool: aiomysql.Pool,
    table: str,
    columns: list[str],
    data: list[tuple],
    batch_size: int = BATCH_SIZE,
    ignore: bool = True,
) -> int:
    """대량 INSERT를 배치 단위로 실행.

    한 배치의 모든 행을 하나의 INSERT 문에 담아 실행하여
    네트워크 왕복을 최소화합니다.

    Args:
        pool: aiomysql 커넥션 풀
        table: 대상 테이블명
        columns: 컬럼 이름 리스트
        data: 삽입할 튜플 리스트
        batch_size: 배치당 행 수
        ignore: INSERT IGNORE 사용 여부

    Returns:
        삽입 성공 행 수 합계
    """
    if not data:
        return 0

    cols_str = ", ".join(columns)
    n_cols = len(columns)
    single_row_placeholder = "(" + ", ".join(["%s"] * n_cols) + ")"
    ignore_str = " IGNORE" if ignore else ""
    total_inserted = 0
    total_batches = math.ceil(len(data) / batch_size)

    for batch_idx in range(total_batches):
        start = batch_idx * batch_size
        end = min(start + batch_size, len(data))
        batch = data[start:end]

        # 다중 행 VALUES 절 생성
        values_str = ", ".join([single_row_placeholder] * len(batch))
        sql = f"INSERT{ignore_str} INTO {table} ({cols_str}) VALUES {values_str}"

        # 튜플 리스트를 평탄화
        flat_params: list[object] = []
        for row in batch:
            flat_params.extend(row)

        conn = await pool.acquire()
        try:
            async with conn.cursor() as cur:
                await cur.execute("BEGIN")
                try:
                    await cur.execute(sql, flat_params)
                    affected = cur.rowcount
                    await cur.execute("COMMIT")
                    total_inserted += affected
                except Exception as e:
                    await cur.execute("ROLLBACK")
                    print(f"  [경고] {table} 배치 {batch_idx + 1}/{total_batches} 실패: {e}")
        finally:
            pool.release(conn)

        # 이벤트 루프 양보
        await asyncio.sleep(0)

    return total_inserted


# ─────────────────────────────────────────────
# 시간 분포 헬퍼
# ─────────────────────────────────────────────


def growth_curve_timestamp(max_days: int = 365) -> datetime:
    """최근에 가중치를 둔 이차 분포 타임스탬프.

    r = random() ** 2 → 0에 가까운 값이 많음 → 최근 날짜가 많이 생성됨.
    """
    r = random.random() ** 2
    days_ago = r * max_days
    return datetime.now(UTC) - timedelta(
        days=days_ago,
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
        seconds=random.randint(0, 59),
    )


def recent_timestamp(max_days: int = 7) -> datetime:
    """최근 N일 내 균등 분포 타임스탬프 (추천 피드 후보용)."""
    return datetime.now(UTC) - timedelta(
        days=random.uniform(0, max_days),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
        seconds=random.randint(0, 59),
    )


# ─────────────────────────────────────────────
# 사용자 티어 헬퍼
# ─────────────────────────────────────────────


def get_user_tier(user_id: int) -> str:
    """사용자 ID로 티어 반환."""
    if user_id <= POWER_COUNT:
        return "power"
    elif user_id <= POWER_COUNT + REGULAR_COUNT:
        return "regular"
    else:
        return "reader"


def weighted_user_id(power_weight: float = 0.4, regular_weight: float = 0.4) -> int:
    """티어 가중치에 따른 랜덤 사용자 ID 반환.

    기본: power 40%, regular 40%, reader 20%
    → power 사용자가 활동의 대부분을 차지하도록 설계.
    """
    roll = random.random()
    if roll < power_weight:
        return random.choice(POWER_IDS)
    elif roll < power_weight + regular_weight:
        return random.choice(REGULAR_IDS)
    else:
        return random.choice(READER_IDS)


# ─────────────────────────────────────────────
# 진행률 표시 헬퍼
# ─────────────────────────────────────────────


def progress(current: int, total: int, label: str = "") -> None:
    """콘솔 진행률 바 출력."""
    if total <= 0:
        return
    pct = current / total
    bar_len = 30
    filled = int(bar_len * pct)
    bar = "\u2588" * filled + "\u2591" * (bar_len - filled)
    suffix = f" {label}" if label else ""
    print(f"\r  {bar} {pct * 100:5.1f}%{suffix}", end="", flush=True)
    if current >= total:
        print()  # 완료 시 개행


# ─────────────────────────────────────────────
# CLI 인자 파서
# ─────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    """커맨드 라인 인자 파싱."""
    parser = argparse.ArgumentParser(
        description="대규모 시드 데이터 생성 (5만 사용자, 15만 게시글 등)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
예시:
  # 로컬 MySQL
  python core/database/seed_data_large.py --db-user root --db-password root --db-port 3306

  # SSH 터널 경유 RDS (기본 포트 3307)
  python core/database/seed_data_large.py --db-user admin --db-password SECRET

  # 기존 데이터 삭제 후 시딩
  python core/database/seed_data_large.py --db-user admin --db-password SECRET --clean --no-confirm
""",
    )
    parser.add_argument("--db-host", default="127.0.0.1", help="DB 호스트 (기본: 127.0.0.1)")
    parser.add_argument("--db-port", type=int, default=3307, help="DB 포트 (기본: 3307, SSH 터널용)")
    parser.add_argument("--db-user", required=True, help="DB 사용자명")
    parser.add_argument("--db-password", required=True, help="DB 비밀번호")
    parser.add_argument("--db-name", default="community_service", help="DB 이름 (기본: community_service)")
    parser.add_argument("--no-confirm", action="store_true", help="확인 프롬프트 생략")
    parser.add_argument("--clean", action="store_true", help="시딩 전 기존 데이터 TRUNCATE")
    parser.add_argument("--dry-run", action="store_true", help="DB 접속 없이 설정 확인만")
    parser.add_argument("--recompute-url", default=None, help="시딩 후 추천 피드 재계산 API URL")
    return parser.parse_args()


# ─────────────────────────────────────────────
# 게시글 콘텐츠 상수
# ─────────────────────────────────────────────

TOTAL_POSTS = 250_000

TITLE_PREFIXES = [
    "Ubuntu 업그레이드 후기",
    "Arch 설치 삽질기",
    "Fedora Wayland 경험",
    "NVIDIA 드라이버 설치",
    "i3wm 설정 공유",
    "systemd 서비스 만들기",
    "내 dotfiles 공유",
    "리눅스 면접 준비 정리",
    "커널 패닉 복구",
    "ZFS vs Btrfs 비교",
    "WSL2 개발 환경 세팅",
    "SSH 터널링 활용법",
    "Vim 플러그인 추천",
    "Docker 컨테이너 경량화",
    "리눅스 보안 강화",
    "GRUB 커스텀 테마",
    "Flatpak vs Snap 비교",
    "tmux 설정 공유",
    "Ansible로 서버 관리",
    "리눅스 데스크톱 쇼케이스",
    "커널 컴파일 후기",
    "Wayland 전환 현황",
    "네트워크 트러블슈팅",
    "iptables 설정 가이드",
    "Btrfs 스냅샷 활용",
    "KDE Plasma 커스텀",
    "GNOME 확장 추천",
    "LVM 파티션 관리",
    "Podman vs Docker",
    "리눅스 서버 모니터링",
    "SELinux 입문",
    "AppArmor 설정",
    "Cron 작업 자동화",
    "NFS 마운트 설정",
    "WireGuard VPN 구축",
    "Proxmox 가상화",
    "Raspberry Pi 프로젝트",
    "리눅스 백업 전략",
    "파일 권한 관리",
    "Neovim 설정 공유",
]

TITLE_SUFFIXES = [
    "공유합니다",
    "질문입니다",
    "후기",
    "정리",
    "가이드",
    "삽질기",
    "해결 방법",
    "비교 분석",
    "추천",
    "경험담",
    "팁",
    "트러블슈팅",
    "설정법",
    "",
    "",
    "",
    "",
    "",
    "",
]

MARKDOWN_CONTENTS = [
    "## Ubuntu 24.04 LTS 업그레이드 후기\n\n드디어 Noble Numbat으로 업그레이드했습니다.\n\n### 달라진 점\n- **GNOME 46** — 파일 관리자 속도 체감\n- **Linux Kernel 6.8** — 하드웨어 호환성 개선\n\n```bash\nsudo apt update && sudo apt full-upgrade\nsudo do-release-upgrade\n```\n\n> 클린 설치보다 업그레이드가 편하긴 한데, 기존 PPA 충돌만 조심하세요!",
    "Arch Linux를 메인으로 쓴 지 1년이 됐습니다.\n\n**Rolling Release**의 장단점을 체감하고 있습니다.\n\n| 항목 | 장점 | 단점 |\n|------|------|------|\n| 패키지 | 항상 최신 | 가끔 깨짐 |\n| 커스텀 | 완전한 자유 | 직접 해야 함 |\n| 문서 | Arch Wiki 최강 | 러닝 커브 높음 |\n\n`pacman -Syu` 한 방이면 전체 시스템이 최신 상태가 되는 게 매력입니다.",
    "### i3wm 타일링 윈도우 매니저 설정 공유\n\n데스크톱 환경 없이 i3wm만 쓰고 있습니다.\n\n1. **i3-gaps** — 창 사이 간격 설정\n2. **polybar** — 상태 바 커스텀\n3. **rofi** — 앱 런처\n\n```bash\nbindsym $mod+Return exec alacritty\nbindsym $mod+d exec rofi -show drun\nbindsym $mod+Shift+q kill\n```",
    "## systemd 서비스 직접 만들기\n\n```ini\n[Unit]\nDescription=My Application\nAfter=network.target\n\n[Service]\nType=simple\nUser=www-data\nExecStart=/opt/myapp/run.sh\nRestart=on-failure\nRestartSec=5\n\n[Install]\nWantedBy=multi-user.target\n```\n\n> `Restart=on-failure`와 `RestartSec`을 꼭 설정하세요.",
    "NVIDIA 드라이버 삽질기를 공유합니다.\n\n### 증상\nUbuntu에서 `nvidia-smi` 실행 시 `No devices were found` 에러.\n\n### 해결\n```bash\nsudo mokutil --import /var/lib/dkms/mok.pub\n# 재부팅 후 MOK Manager에서 Enroll 선택\n```\n\nSecure Boot가 서명되지 않은 커널 모듈을 차단한 것이 원인이었습니다.",
    '프론트엔드 개발할 때 WSL2 + Docker 조합이 편합니다.\n\n- **WSL2 Ubuntu** 안에서 개발 서버 실행\n- VS Code **Remote - WSL** 확장\n- `localhost` 포워딩 자동 지원\n\n```bash\ndocker info | grep "Operating System"\n# Docker Desktop (WSL2 backend)\n```\n\nWindows 파일시스템(`/mnt/c/`)에서 작업하면 느리니 `~/` 아래에서 작업하세요.',
    "## 내 dotfiles 관리 방법\n\nbare Git repo로 관리합니다.\n\n```bash\ngit init --bare $HOME/.dotfiles\nalias dotgit='git --git-dir=$HOME/.dotfiles --work-tree=$HOME'\ndotgit add ~/.bashrc ~/.config/i3/config\ndotgit commit -m \"i3 키바인딩 업데이트\"\n```\n\nStow나 chezmoi보다 간단하고, 별도 도구 설치가 필요 없어서 좋습니다.",
    "취업 준비하면서 정리한 **리눅스 면접 필수 개념**입니다.\n\n### 프로세스\n- `fork()` vs `exec()` vs `clone()`\n- 좀비 프로세스와 고아 프로세스\n\n### 파일 시스템\n- inode 구조, 하드링크 vs 심볼릭링크\n- `/proc`, `/sys` 가상 파일시스템\n\n### 네트워크\n- iptables/nftables 규칙 구조\n- TCP 3-way handshake, TIME_WAIT",
]

PLAIN_CONTENTS = [
    "오늘 커널 업데이트 후 부팅이 안 돼서 GRUB에서 이전 커널로 복구했습니다. 스냅샷 꼭 남기세요.",
    "Fedora 40에서 Wayland가 기본이 됐는데, X11 전용 앱들이 XWayland로 잘 돌아가더라고요.",
    "리눅스 민트에서 우분투로 갈아탔는데, Cinnamon이 그립습니다. GNOME은 확장 없이는 좀 불편하네요.",
    "ZFS on Linux 써보신 분? 스냅샷이랑 압축이 좋다는데 메모리를 많이 먹는다고 해서 고민됩니다.",
    "오늘 처음으로 Arch 설치에 성공했습니다! archinstall 안 쓰고 수동으로 했는데 뿌듯하네요.",
    "서버 관리할 때 Ansible이랑 셸 스크립트 중에 뭐가 나을까요? 서버 5대 정도 규모입니다.",
    "tmux 설정 공유합니다. prefix를 Ctrl+a로 바꾸고 마우스 모드 켜면 훨씬 편합니다.",
    "Flatpak vs Snap 논쟁이 다시 시작됐네요. 개인적으로 Flatpak이 더 가볍게 느껴집니다.",
]

# ─────────────────────────────────────────────
# 게시글 헬퍼
# ─────────────────────────────────────────────

TOTAL_POLLS = 2_500

POLL_QUESTIONS = [
    ("선호하는 리눅스 배포판은?", ["Ubuntu", "Fedora", "Arch", "Debian", "기타"]),
    ("데스크톱 환경 선호도", ["GNOME", "KDE Plasma", "XFCE", "i3/Sway", "없음 (TTY)"]),
    ("주로 사용하는 셸은?", ["Bash", "Zsh", "Fish", "Nushell"]),
    ("에디터 선호도", ["Vim/Neovim", "Emacs", "VS Code", "nano", "기타"]),
    ("패키지 설치 선호도", ["공식 저장소", "Flatpak", "Snap", "AppImage", "직접 빌드"]),
    ("디스플레이 서버", ["Wayland", "X11", "상관없음", "잘 모르겠음"]),
    ("리눅스 경력은?", ["1년 미만", "1~3년", "3~5년", "5년 이상"]),
    ("서버 OS 선호도", ["Ubuntu Server", "RHEL/Rocky", "Debian", "Alpine"]),
    ("파일 시스템 선호도", ["ext4", "Btrfs", "ZFS", "XFS"]),
    ("리눅스를 쓰는 이유?", ["오픈소스 철학", "커스텀 자유도", "개발 편의성", "서버 운영", "보안"]),
    ("터미널 에뮬레이터 선호도", ["Alacritty", "kitty", "GNOME Terminal", "Konsole", "WezTerm"]),
    ("컨테이너 런타임", ["Docker", "Podman", "containerd", "안 씀"]),
    ("가상화 도구 선호도", ["VirtualBox", "KVM/QEMU", "Proxmox", "VMware", "안 씀"]),
    ("백업 전략", ["rsync", "Timeshift", "Btrfs 스냅샷", "클라우드", "안 함"]),
    ("네트워크 VPN", ["WireGuard", "OpenVPN", "Tailscale", "안 씀"]),
    ("init 시스템 선호도", ["systemd", "OpenRC", "runit", "상관없음"]),
    ("리눅스 학습 방법", ["Arch Wiki", "공식 문서", "유튜브", "직접 삽질"]),
    ("커널 컴파일 해봤나요?", ["자주 함", "한 번 해봄", "관심 있음", "필요 없음"]),
    ("모니터링 도구", ["htop/btop", "Prometheus+Grafana", "Netdata", "glances"]),
    ("AUR 사용하시나요?", ["매일", "가끔", "Arch 안 씀", "AUR이 뭔가요"]),
    ("윈도우 매니저 타입", ["플로팅 (GNOME/KDE)", "타일링 (i3/Sway)", "둘 다", "TTY"]),
    ("리눅스 게이밍", ["Steam+Proton", "Lutris", "네이티브만", "게임 안 함"]),
    ("선호하는 부트로더", ["GRUB", "systemd-boot", "rEFInd", "상관없음"]),
    ("dotfiles 관리 방법", ["Git bare repo", "Stow", "chezmoi", "관리 안 함"]),
    ("DNS 서버 설정", ["systemd-resolved", "dnsmasq", "직접 설정", "기본값"]),
    ("Wayland 만족도", ["매우 만족", "보통", "불만족", "아직 X11"]),
    ("리눅스 보안 도구", ["SELinux", "AppArmor", "Firejail", "없음"]),
    ("CI/CD 도구", ["GitHub Actions", "GitLab CI", "Jenkins", "기타"]),
    ("좋아하는 커맨드라인 도구", ["ripgrep", "fzf", "bat", "exa/eza"]),
    ("리눅스 커뮤니티 활동", ["포럼 참여", "블로그 운영", "오픈소스 기여", "읽기만"]),
]

# 전역 변수: poll_votes에서 사용
_poll_options_map: dict[int, list[int]] = {}

POSTS_POWER_AVG = 40  # 파워유저 평균 게시글
POSTS_REGULAR_AVG = 10  # 일반유저 평균
POSTS_READER_AVG = 0.7  # 읽기전용 평균


def _generate_title(idx: int) -> str:
    """고유 제목 생성."""
    prefix = random.choice(TITLE_PREFIXES)
    suffix = random.choice(TITLE_SUFFIXES)
    if suffix:
        return f"{prefix} {suffix} #{idx}"
    return f"{prefix} #{idx}"


def _generate_content() -> str:
    """게시글 본문 생성."""
    r = random.random()
    if r < 0.2:  # 20% 마크다운
        return random.choice(MARKDOWN_CONTENTS)
    elif r < 0.5:  # 30% 짧은 글
        return random.choice(PLAIN_CONTENTS)
    else:  # 50% 중간 (plain + faker paragraph)
        base = random.choice(PLAIN_CONTENTS)
        extra = fake.paragraph(nb_sentences=random.randint(2, 5))
        return f"{base}\n\n{extra}"


def _assign_author_for_posts() -> list[int]:
    """계층별 비율에 맞게 게시글 작성자 ID 리스트 생성.

    파워유저: ~40개/인 × 2,500명 = ~100,000
    일반유저: ~10개/인 × 12,500명 = ~125,000
    읽기전용: ~0.7개/인 × 35,000명 = ~25,000
    합계 ~250,000
    """
    authors = []

    for uid in POWER_IDS:
        count = max(1, int(random.gauss(POSTS_POWER_AVG, 10)))
        authors.extend([uid] * count)

    for uid in REGULAR_IDS:
        count = max(0, int(random.gauss(POSTS_REGULAR_AVG, 3)))
        authors.extend([uid] * count)

    for uid in READER_IDS:
        if random.random() < POSTS_READER_AVG:
            authors.append(uid)

    random.shuffle(authors)

    # Trim or pad to TOTAL_POSTS
    if len(authors) > TOTAL_POSTS:
        authors = authors[:TOTAL_POSTS]
    while len(authors) < TOTAL_POSTS:
        authors.append(weighted_user_id(0.5, 0.35))

    return authors


def _tag_id_powerlaw() -> int:
    """멱법칙 분포로 태그 ID 반환. 인기 태그 10개가 50% 차지."""
    r = random.random()
    if r < 0.50:
        return random.randint(1, 10)
    elif r < 0.80:
        return random.randint(11, 25)
    else:
        return random.randint(26, len(TAG_NAMES))


# ─────────────────────────────────────────────
# 인터랙션 상수
# ─────────────────────────────────────────────

TOTAL_COMMENTS = 750_000
TOTAL_POST_LIKES = 500_000
TOTAL_BOOKMARKS = 150_000
TOTAL_COMMENT_LIKES = 300_000
TOTAL_VIEW_LOGS = 500_000
TOTAL_POLL_VOTES = 50_000

TOTAL_FOLLOWS = 100_000
TOTAL_BLOCKS = 2_500
TOTAL_NOTIFICATIONS = 500_000
TOTAL_REPORTS = 2_500
TOTAL_DM_CONVERSATIONS = 5_000
DM_MESSAGES_PER_CONV = 15
REPORT_REASONS = ["spam", "abuse", "inappropriate", "other"]

COMMENT_TEMPLATES = [
    "좋은 글 감사합니다! 저도 같은 배포판 쓰고 있어요.",
    "`sudo apt update` 먼저 실행해보셨나요?",
    "저는 Arch Wiki에서 해결했어요. 참고해보세요.",
    "Fedora에서도 같은 방법으로 됩니다.",
    "커널 버전이 뭔가요? `uname -r`로 확인해주세요.",
    "저도 비슷한 경험이 있어요. Secure Boot 끄니까 해결됐습니다.",
    "참고하겠습니다! dotfiles 레포 주소 공유 가능하신가요?",
    "Wayland에서는 안 되는 거 아닌가요?",
    "좋은 정보네요. 이 설정 그대로 적용했습니다.",
    "`journalctl -xe`로 로그 확인해보세요.",
    "저는 좀 다른 방법을 쓰는데, 나중에 글로 정리해볼게요.",
    "우분투에서 데비안으로 갈아탈까 고민 중인데 참고가 됩니다.",
    "응원합니다! Arch 수동 설치 성공하면 뿌듯하죠.",
    "이건 `man` 페이지에도 잘 나와 있어요.",
    "실무에서도 이렇게 하시나요? 프로덕션 서버에서는 좀 다를 것 같아서요.",
    "정리가 잘 되어 있네요. 북마크했습니다.",
    "저도 같은 삽질을 했어요. 결국 Arch Wiki가 답이더라고요.",
    "이 방법은 systemd 기반에서만 되나요?",
    "`dmesg | tail`로 확인해보시면 원인이 보일 겁니다.",
    "Wayland 전환하니까 이 문제가 해결됐어요.",
]


def _popular_post_id() -> int:
    """인기 편중 게시글 ID: 상위 5%가 좋아요 40% 수신."""
    top_5_pct = max(1, int(TOTAL_POSTS * 0.05))
    if random.random() < 0.4:
        return random.randint(1, top_5_pct)
    return random.randint(1, TOTAL_POSTS)


# ─────────────────────────────────────────────
# 스텁 함수 (후속 Task에서 구현)
# ─────────────────────────────────────────────


async def clean_all_data(pool: aiomysql.Pool) -> None:
    """기존 데이터 전체 삭제 (TRUNCATE).

    FK 안전 순서로 모든 테이블을 TRUNCATE한 뒤 카테고리 시드를 재삽입합니다.
    """
    # FK 자식 → 부모 순서 (31테이블 전체 커버)
    tables = [
        "user_post_score",
        "wiki_page_tag",
        "wiki_page",
        "package_review",
        "package",
        "dm_message",
        "dm_conversation",
        "poll_vote",
        "poll_option",
        "poll",
        "post_tag",
        "tag",
        "user_follow",
        "user_block",
        "comment_like",
        "post_bookmark",
        "post_image",
        "notification_setting",
        "notification",
        "report",
        "post_view_log",
        "post_like",
        "comment",
        "post_draft",
        "post",
        "social_account",
        "email_verification",
        "refresh_token",
        "image",
        "category",
        "user",
    ]

    async with pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute("SET FOREIGN_KEY_CHECKS = 0")
        try:
            for table in tables:
                await cur.execute(f"TRUNCATE TABLE {table}")
                print(f"  TRUNCATE {table}")
        finally:
            await cur.execute("SET FOREIGN_KEY_CHECKS = 1")

        # 카테고리 시드 재삽입
        await cur.execute("""
                INSERT INTO category (name, slug, description, sort_order) VALUES
                    ('배포판', 'distro', 'Ubuntu, Fedora, Arch 등 배포판별 토론 공간입니다.', 1),
                    ('Q&A', 'qna', '리눅스 트러블슈팅, 설치, 설정 관련 질문과 답변입니다.', 2),
                    ('뉴스/소식', 'news', '리눅스 생태계의 최신 소식을 공유합니다.', 3),
                    ('프로젝트/쇼케이스', 'showcase', 'dotfiles, 스크립트, 오픈소스 기여를 공유합니다.', 4),
                    ('팁/가이드', 'guide', '리눅스 튜토리얼과 How-to 가이드입니다.', 5),
                    ('공지사항', 'notice', '관리자 공지사항입니다.', 6)
            """)
        print("  카테고리 시드 재삽입 완료 (6개)")
    print("  전체 TRUNCATE 완료")


async def seed_categories(pool: aiomysql.Pool) -> None:
    """카테고리 시드 데이터 삽입.

    이미 6개 이상 존재하면 스킵합니다.
    """
    async with pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute("SELECT COUNT(*) FROM category")
        (count,) = await cur.fetchone()

    if count >= 6:
        print(f"  카테고리: 이미 {count}개 존재 — 스킵")
        return

    data = [
        ("배포판", "distro", "Ubuntu, Fedora, Arch 등 배포판별 토론 공간입니다.", 1),
        ("Q&A", "qna", "리눅스 트러블슈팅, 설치, 설정 관련 질문과 답변입니다.", 2),
        ("뉴스/소식", "news", "리눅스 생태계의 최신 소식을 공유합니다.", 3),
        ("프로젝트/쇼케이스", "showcase", "dotfiles, 스크립트, 오픈소스 기여를 공유합니다.", 4),
        ("팁/가이드", "guide", "리눅스 튜토리얼과 How-to 가이드입니다.", 5),
        ("공지사항", "notice", "관리자 공지사항입니다.", 6),
    ]
    inserted = await batch_insert_raw(
        pool,
        "category",
        ["name", "slug", "description", "sort_order"],
        data,
        ignore=True,
    )
    print(f"  카테고리: {inserted}개 삽입")


async def seed_tags(pool: aiomysql.Pool) -> None:
    """태그 50개 삽입 (INSERT IGNORE)."""
    data = [(name,) for name in TAG_NAMES]
    inserted = await batch_insert_raw(
        pool,
        "tag",
        ["name"],
        data,
        ignore=True,
    )
    print(f"  태그: {inserted}개 삽입 (총 {len(TAG_NAMES)}개 시도)")


async def seed_users(pool: aiomysql.Pool) -> None:
    """사용자 5만 명 생성.

    user 1은 admin 역할, 나머지는 일반 사용자.
    전원 이메일 인증 완료 상태, distro 분포 포함.
    """
    print(f"  사용자 데이터 생성 중 ({TOTAL_USERS:,}명)...")
    distro_pool = random.choices(DISTROS, weights=DISTRO_WEIGHTS, k=TOTAL_USERS)
    data: list[tuple] = []
    for i in range(1, TOTAL_USERS + 1):
        email = f"user{i}@example.com"
        nickname = f"user_{i:05d}"
        role = "admin" if i == 1 else "user"
        distro = distro_pool[i - 1]
        created_at = growth_curve_timestamp(365)
        data.append((email, 1, nickname, 1, HASHED_PASSWORD, role, distro, created_at, created_at))

        # 생성 진행률 표시 (1만 명마다)
        if i % 10_000 == 0:
            print(f"    생성: {i:>6,} / {TOTAL_USERS:,}")

    print("  사용자 INSERT 시작...")
    inserted = await batch_insert_raw(
        pool,
        "user",
        [
            "email",
            "email_verified",
            "nickname",
            "nickname_set",
            "password",
            "role",
            "distro",
            "created_at",
            "terms_agreed_at",
        ],
        data,
        ignore=True,
    )
    print(f"  사용자: {inserted:,}명 삽입 완료")


async def seed_posts(pool: aiomysql.Pool) -> None:
    """게시글 ~250,000개 생성 (성장 곡선 + 계층별 분포)."""
    print(f"  게시글 {TOTAL_POSTS:,}개 생성 중...")

    authors = _assign_author_for_posts()
    data = []

    # 최근 7일 게시글 비율 (~8% = 20,000개) — 피드 후보 풀 확보
    recent_count = int(TOTAL_POSTS * 0.08)

    for i in range(TOTAL_POSTS):
        post_idx = i + 1
        author_id = authors[i]
        title = _generate_title(post_idx)
        content = _generate_content()
        views = random.randint(0, 500)

        # 카테고리: 공지사항(id=6)은 admin(user1)만
        if author_id == 1:
            category_id = random.randint(1, 6)
        else:
            r = random.random()
            if r < 0.25:
                category_id = 1  # 배포판 25%
            elif r < 0.45:
                category_id = 2  # Q&A 20%
            elif r < 0.60:
                category_id = 3  # 뉴스/소식 15%
            elif r < 0.80:
                category_id = 4  # 프로젝트/쇼케이스 20%
            else:
                category_id = 5  # 팁/가이드 20%

        # 시간: 8%는 최근 7일 (피드 후보), 나머지는 성장 곡선
        if i < recent_count:
            created_at = recent_timestamp(7)
        else:
            created_at = growth_curve_timestamp(365)

        data.append((title, content, None, author_id, category_id, views, created_at))

        if (i + 1) % 50_000 == 0:
            progress(i + 1, TOTAL_POSTS, "게시글 데이터 생성")

    progress(TOTAL_POSTS, TOTAL_POSTS, "게시글 데이터 생성")

    count = await batch_insert_raw(
        pool,
        "post",
        ["title", "content", "image_url", "author_id", "category_id", "views", "created_at"],
        data,
        ignore=False,  # post 테이블에 UNIQUE 제약 없음
    )
    print(f"  ✓ 게시글 {count:,}개 삽입 완료")


async def seed_post_tags(pool: aiomysql.Pool) -> None:
    """게시글-태그 연결 생성 (70%의 게시글에 1~3개 태그)."""
    print("  게시글-태그 데이터 생성 중...")
    data: list[tuple] = []

    for post_id in range(1, TOTAL_POSTS + 1):
        if random.random() >= 0.70:
            continue
        tag_count = random.randint(1, 3)
        used_tags: set[int] = set()
        for _ in range(tag_count):
            tag_id = _tag_id_powerlaw()
            if tag_id not in used_tags:
                used_tags.add(tag_id)
                data.append((post_id, tag_id))

    count = await batch_insert_raw(
        pool,
        "post_tag",
        ["post_id", "tag_id"],
        data,
        ignore=True,
    )
    print(f"  게시글-태그: {count:,}개 삽입 완료")


async def seed_post_images(pool: aiomysql.Pool) -> None:
    """게시글 이미지 연결 생성 (20%의 게시글에 1~3개 이미지)."""
    print("  게시글 이미지 데이터 생성 중...")
    data: list[tuple] = []

    for post_id in range(1, TOTAL_POSTS + 1):
        if random.random() >= 0.20:
            continue
        img_count = random.randint(1, 3)
        for order in range(img_count):
            image_url = f"/uploads/posts/{post_id}_{order + 1}.jpg"
            data.append((post_id, image_url, order))

    count = await batch_insert_raw(
        pool,
        "post_image",
        ["post_id", "image_url", "sort_order"],
        data,
        ignore=False,
    )
    print(f"  게시글 이미지: {count:,}개 삽입 완료")


async def seed_polls(pool: aiomysql.Pool) -> None:
    """투표 데이터 생성 (2,500개 투표 + 선택지)."""
    global _poll_options_map
    print(f"  투표 데이터 생성 중 ({TOTAL_POLLS:,}개)...")

    poll_post_ids = random.sample(range(1, TOTAL_POSTS + 1), TOTAL_POLLS)
    poll_count = 0
    option_count = 0

    conn = await pool.acquire()
    try:
        async with conn.cursor() as cur:
            await cur.execute("BEGIN")
            try:
                for i, post_id in enumerate(poll_post_ids):
                    question, options = random.choice(POLL_QUESTIONS)

                    # 50%는 만료일 설정
                    if random.random() < 0.50:
                        expires_at = datetime.now(UTC) + timedelta(
                            days=random.randint(1, 30),
                        )
                    else:
                        expires_at = None

                    created_at = growth_curve_timestamp(365)

                    await cur.execute(
                        "INSERT IGNORE INTO poll (post_id, question, expires_at, created_at) VALUES (%s, %s, %s, %s)",
                        (post_id, question, expires_at, created_at),
                    )
                    poll_id = cur.lastrowid

                    if poll_id == 0:
                        # INSERT IGNORE로 중복 스킵된 경우
                        continue

                    poll_count += 1
                    option_ids: list[int] = []

                    for opt_text in options:
                        await cur.execute(
                            "INSERT INTO poll_option (poll_id, option_text) VALUES (%s, %s)",
                            (poll_id, opt_text),
                        )
                        option_ids.append(cur.lastrowid)
                        option_count += 1

                    _poll_options_map[poll_id] = option_ids

                    # 500건마다 커밋
                    if (i + 1) % 500 == 0:
                        await cur.execute("COMMIT")
                        await cur.execute("BEGIN")
                        progress(i + 1, TOTAL_POLLS, "투표 생성")

                await cur.execute("COMMIT")
            except Exception:
                await cur.execute("ROLLBACK")
                raise

    finally:
        pool.release(conn)

    progress(TOTAL_POLLS, TOTAL_POLLS, "투표 생성")
    print(f"  투표: {poll_count:,}개, 선택지: {option_count:,}개 삽입 완료")


async def seed_comments(pool: aiomysql.Pool) -> None:
    """댓글 ~750,000개 생성 (80% 루트 + 20% 대댓글)."""
    root_count = int(TOTAL_COMMENTS * 0.8)
    reply_count = TOTAL_COMMENTS - root_count
    print(f"  댓글 {TOTAL_COMMENTS:,}개 생성 중 (루트 {root_count:,}, 대댓글 {reply_count:,})...")

    # 루트 댓글 — 메모리 절약을 위해 50,000개씩 배치 생성/삽입
    ROOT_GEN_BATCH = 50_000
    count1 = 0
    for batch_start in range(0, root_count, ROOT_GEN_BATCH):
        batch_end = min(batch_start + ROOT_GEN_BATCH, root_count)
        root_data = []
        for _ in range(batch_end - batch_start):
            content = random.choice(COMMENT_TEMPLATES) + " " + fake.sentence()
            author_id = weighted_user_id(0.4, 0.35)
            post_id = random.randint(1, TOTAL_POSTS)
            created_at = growth_curve_timestamp(180)
            root_data.append((content, author_id, post_id, None, created_at))

        count1 += await batch_insert_raw(
            pool,
            "comment",
            ["content", "author_id", "post_id", "parent_id", "created_at"],
            root_data,
            ignore=False,
        )
        progress(batch_end, root_count, "루트 댓글")

    # 대댓글 — parent_id의 post_id를 배치 조회
    async with pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute("SELECT MIN(id), MAX(id) FROM comment WHERE parent_id IS NULL")
        row = await cur.fetchone()
        if not row or not row[0]:
            print(f"  ✓ 댓글 {count1:,}개 (루트만)")
            return
        min_root_id, max_root_id = row

    # 대댓글을 배치로 생성: parent_id들의 post_id를 한번에 조회
    REPLY_BATCH = 10_000
    reply_data: list[tuple] = []
    for batch_start in range(0, reply_count, REPLY_BATCH):
        batch_end = min(batch_start + REPLY_BATCH, reply_count)
        batch_parent_ids = [random.randint(min_root_id, max_root_id) for _ in range(batch_end - batch_start)]

        placeholders = ",".join(["%s"] * len(batch_parent_ids))
        async with pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute(
                f"SELECT id, post_id FROM comment WHERE id IN ({placeholders})",
                batch_parent_ids,
            )
            parent_map = {r[0]: r[1] for r in await cur.fetchall()}

        for parent_id in batch_parent_ids:
            mapped_post_id = parent_map.get(parent_id)
            if not mapped_post_id:
                continue
            content = random.choice(COMMENT_TEMPLATES) + " " + fake.sentence()
            author_id = weighted_user_id(0.4, 0.35)
            created_at = growth_curve_timestamp(90)
            reply_data.append((content, author_id, mapped_post_id, parent_id, created_at))

    count2 = 0
    if reply_data:
        count2 = await batch_insert_raw(
            pool,
            "comment",
            ["content", "author_id", "post_id", "parent_id", "created_at"],
            reply_data,
            ignore=False,
        )
    print(f"  ✓ 댓글 {count1 + count2:,}개 (루트 {count1:,}, 대댓글 {count2:,})")


async def seed_post_likes(pool: aiomysql.Pool) -> None:
    """게시글 좋아요 ~500,000개 생성 (인기 편중 분포)."""
    print(f"  게시글 좋아요 {TOTAL_POST_LIKES:,}개 생성 중...")
    seen: set[tuple[int, int]] = set()
    data: list[tuple] = []
    max_attempts = TOTAL_POST_LIKES * 3
    attempts = 0

    while len(data) < TOTAL_POST_LIKES and attempts < max_attempts:
        attempts += 1
        user_id = weighted_user_id(0.3, 0.4)
        post_id = _popular_post_id()
        key = (user_id, post_id)
        if key in seen:
            continue
        seen.add(key)
        created_at = growth_curve_timestamp(180)
        data.append((user_id, post_id, created_at))

    count = await batch_insert_raw(
        pool,
        "post_like",
        ["user_id", "post_id", "created_at"],
        data,
        ignore=True,
    )
    print(f"  ✓ 게시글 좋아요 {count:,}개 삽입 완료")


async def seed_bookmarks(pool: aiomysql.Pool) -> None:
    """북마크 ~150,000개 생성."""
    print(f"  북마크 {TOTAL_BOOKMARKS:,}개 생성 중...")
    seen: set[tuple[int, int]] = set()
    data: list[tuple] = []
    max_attempts = TOTAL_BOOKMARKS * 3
    attempts = 0

    while len(data) < TOTAL_BOOKMARKS and attempts < max_attempts:
        attempts += 1
        user_id = weighted_user_id(0.4, 0.4)
        post_id = _popular_post_id()
        key = (user_id, post_id)
        if key in seen:
            continue
        seen.add(key)
        created_at = growth_curve_timestamp(180)
        data.append((user_id, post_id, created_at))

    count = await batch_insert_raw(
        pool,
        "post_bookmark",
        ["user_id", "post_id", "created_at"],
        data,
        ignore=True,
    )
    print(f"  ✓ 북마크 {count:,}개 삽입 완료")


async def seed_comment_likes(pool: aiomysql.Pool) -> None:
    """댓글 좋아요 ~300,000개 생성."""
    print(f"  댓글 좋아요 {TOTAL_COMMENT_LIKES:,}개 생성 중...")

    # 댓글 ID 범위 조회
    async with pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute("SELECT MAX(id) FROM comment")
        row = await cur.fetchone()
        if not row or not row[0]:
            print("  ✓ 댓글 좋아요 0개 (댓글 없음)")
            return
        max_comment_id = row[0]

    seen: set[tuple[int, int]] = set()
    data: list[tuple] = []
    max_attempts = TOTAL_COMMENT_LIKES * 3
    attempts = 0

    while len(data) < TOTAL_COMMENT_LIKES and attempts < max_attempts:
        attempts += 1
        user_id = weighted_user_id(0.4, 0.35)
        comment_id = random.randint(1, max_comment_id)
        key = (user_id, comment_id)
        if key in seen:
            continue
        seen.add(key)
        created_at = growth_curve_timestamp(180)
        data.append((user_id, comment_id, created_at))

    count = await batch_insert_raw(
        pool,
        "comment_like",
        ["user_id", "comment_id", "created_at"],
        data,
        ignore=True,
    )
    print(f"  ✓ 댓글 좋아요 {count:,}개 삽입 완료")


async def seed_view_logs(pool: aiomysql.Pool) -> None:
    """조회 로그 ~500,000개 생성 (UNIQUE(user_id, post_id, view_date))."""
    print(f"  조회 로그 {TOTAL_VIEW_LOGS:,}개 생성 중...")
    seen: set[tuple[int, int, str]] = set()
    data: list[tuple] = []
    max_attempts = TOTAL_VIEW_LOGS * 3
    attempts = 0

    while len(data) < TOTAL_VIEW_LOGS and attempts < max_attempts:
        attempts += 1
        user_id = weighted_user_id(0.2, 0.3)
        post_id = _popular_post_id()
        created_at = growth_curve_timestamp(30)
        # view_date는 GENERATED 컬럼이므로 직접 삽입하지 않지만
        # 유니크 제약 충돌 방지를 위해 날짜 문자열로 추적
        date_str = created_at.strftime("%Y-%m-%d")
        key = (user_id, post_id, date_str)
        if key in seen:
            continue
        seen.add(key)
        data.append((user_id, post_id, created_at))

    count = await batch_insert_raw(
        pool,
        "post_view_log",
        ["user_id", "post_id", "created_at"],
        data,
        ignore=True,
    )
    print(f"  ✓ 조회 로그 {count:,}개 삽입 완료")


async def seed_poll_votes(pool: aiomysql.Pool) -> None:
    """투표 참여 데이터 ~50,000개 생성."""
    if not _poll_options_map:
        print("  ✓ 투표 참여 0개 (투표 데이터 없음)")
        return

    print(f"  투표 참여 {TOTAL_POLL_VOTES:,}개 생성 중...")
    poll_ids = list(_poll_options_map.keys())
    votes_per_poll = max(1, TOTAL_POLL_VOTES // len(poll_ids))

    seen: set[tuple[int, int]] = set()
    data: list[tuple] = []

    for poll_id in poll_ids:
        option_ids = _poll_options_map[poll_id]
        if not option_ids:
            continue

        # 각 투표당 랜덤 수의 참여자
        num_voters = random.randint(
            max(1, votes_per_poll // 2),
            votes_per_poll * 2,
        )

        for _ in range(num_voters):
            user_id = weighted_user_id(0.3, 0.35)
            key = (poll_id, user_id)
            if key in seen:
                continue
            seen.add(key)
            option_id = random.choice(option_ids)
            created_at = growth_curve_timestamp(180)
            data.append((poll_id, option_id, user_id, created_at))

            if len(data) >= TOTAL_POLL_VOTES:
                break

        if len(data) >= TOTAL_POLL_VOTES:
            break

    count = await batch_insert_raw(
        pool,
        "poll_vote",
        ["poll_id", "option_id", "user_id", "created_at"],
        data,
        ignore=True,
    )
    print(f"  ✓ 투표 참여 {count:,}개 삽입 완료")


async def seed_follows(pool: aiomysql.Pool) -> None:
    """팔로우 ~100,000개 (파워유저 간 높은 상호 팔로우)."""
    print(f"  팔로우 {TOTAL_FOLLOWS:,}개 생성 중...")
    seen: set[tuple[int, int]] = set()
    data: list[tuple] = []

    # 파워유저 간 상호 팔로우 (~2% of pairs)
    power_list = list(POWER_IDS)
    for i in range(len(power_list)):
        if len(data) >= TOTAL_FOLLOWS // 3:
            break
        for j in range(i + 1, len(power_list)):
            if len(data) >= TOTAL_FOLLOWS // 3:
                break
            if random.random() < 0.02:
                a, b = power_list[i], power_list[j]
                if (a, b) not in seen:
                    seen.add((a, b))
                    data.append((a, b, growth_curve_timestamp(180)))
                if (b, a) not in seen:
                    seen.add((b, a))
                    data.append((b, a, growth_curve_timestamp(180)))

    # 나머지: 일반/읽기 → 파워유저 팔로우
    attempts = 0
    while len(data) < TOTAL_FOLLOWS and attempts < TOTAL_FOLLOWS * 3:
        follower = weighted_user_id(0.1, 0.4)
        following = weighted_user_id(0.7, 0.2)
        if follower != following and (follower, following) not in seen:
            seen.add((follower, following))
            data.append((follower, following, growth_curve_timestamp(180)))
        attempts += 1

    count = await batch_insert_raw(
        pool,
        "user_follow",
        ["follower_id", "following_id", "created_at"],
        data[:TOTAL_FOLLOWS],
        ignore=True,
    )
    print(f"  ✓ 팔로우 {count:,}개")


async def seed_blocks(pool: aiomysql.Pool) -> None:
    """사용자 차단 ~2,500개 생성."""
    print(f"  사용자 차단 {TOTAL_BLOCKS:,}개 생성 중...")
    seen: set[tuple[int, int]] = set()
    data: list[tuple] = []
    attempts = 0

    while len(data) < TOTAL_BLOCKS and attempts < TOTAL_BLOCKS * 3:
        blocker = random.randint(1, TOTAL_USERS)
        blocked = random.randint(1, TOTAL_USERS)
        if blocker != blocked and (blocker, blocked) not in seen:
            seen.add((blocker, blocked))
            data.append((blocker, blocked, growth_curve_timestamp(90)))
        attempts += 1

    count = await batch_insert_raw(
        pool,
        "user_block",
        ["blocker_id", "blocked_id", "created_at"],
        data,
        ignore=True,
    )
    print(f"  ✓ 사용자 차단 {count:,}개")


async def seed_notifications(pool: aiomysql.Pool) -> None:
    """알림 ~500,000개 생성."""
    print(f"  알림 {TOTAL_NOTIFICATIONS:,}개 생성 중...")

    # 실제 댓글 MAX(id) 조회 — 대댓글 스킵으로 TOTAL_COMMENTS보다 작을 수 있음
    async with pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute("SELECT MAX(id) FROM comment")
        (max_comment_id,) = await cur.fetchone()
    max_comment_id = max_comment_id or TOTAL_COMMENTS

    # 타입 가중치: comment 20%, like 30%, mention 10%, follow 20%, bookmark 20%
    type_pool = ["comment", "comment", "like", "like", "like", "mention", "follow", "follow", "bookmark", "bookmark"]
    data: list[tuple] = []

    for i in range(TOTAL_NOTIFICATIONS):
        ntype = random.choice(type_pool)
        user_id = weighted_user_id(0.5, 0.3)
        actor_id = weighted_user_id(0.4, 0.35)
        # actor와 user가 같으면 다시 선택
        while actor_id == user_id:
            actor_id = weighted_user_id(0.4, 0.35)
        # follow는 post_id가 NULL
        post_id = None if ntype == "follow" else random.randint(1, TOTAL_POSTS)
        comment_id = random.randint(1, max_comment_id) if ntype in ("comment", "mention") else None
        is_read = 1 if random.random() < 0.7 else 0
        created_at = growth_curve_timestamp(90)
        data.append((user_id, ntype, post_id, comment_id, actor_id, is_read, created_at))

        if (i + 1) % 100_000 == 0:
            progress(i + 1, TOTAL_NOTIFICATIONS, "알림 데이터 생성")

    progress(TOTAL_NOTIFICATIONS, TOTAL_NOTIFICATIONS, "알림 데이터 생성")

    count = await batch_insert_raw(
        pool,
        "notification",
        ["user_id", "type", "post_id", "comment_id", "actor_id", "is_read", "created_at"],
        data,
        ignore=False,
    )
    print(f"  ✓ 알림 {count:,}개")


async def seed_reports(pool: aiomysql.Pool) -> None:
    """신고 ~2,500개 생성."""
    print(f"  신고 {TOTAL_REPORTS:,}개 생성 중...")
    seen: set[tuple[int, str, int]] = set()
    data: list[tuple] = []
    attempts = 0

    while len(data) < TOTAL_REPORTS and attempts < TOTAL_REPORTS * 3:
        attempts += 1
        reporter_id = weighted_user_id(0.3, 0.4)
        target_type = random.choice(["post", "comment"])
        if target_type == "post":
            target_id = random.randint(1, TOTAL_POSTS)
        else:
            target_id = random.randint(1, TOTAL_COMMENTS)

        key = (reporter_id, target_type, target_id)
        if key in seen:
            continue
        seen.add(key)

        reason = random.choice(REPORT_REASONS)
        description = fake.sentence() if reason == "other" else None

        # 상태 분포: ~60% pending, 20% resolved, 20% dismissed
        r = random.random()
        created_at = growth_curve_timestamp(180)
        if r < 0.6:
            status = "pending"
            resolved_by = None
            resolved_at = None
        elif r < 0.8:
            status = "resolved"
            resolved_by = 1  # admin
            resolved_at = created_at + timedelta(days=random.randint(1, 7))
        else:
            status = "dismissed"
            resolved_by = 1  # admin
            resolved_at = created_at + timedelta(days=random.randint(1, 7))

        data.append(
            (reporter_id, target_type, target_id, reason, description, status, resolved_by, resolved_at, created_at)
        )

    count = await batch_insert_raw(
        pool,
        "report",
        [
            "reporter_id",
            "target_type",
            "target_id",
            "reason",
            "description",
            "status",
            "resolved_by",
            "resolved_at",
            "created_at",
        ],
        data,
        ignore=True,
    )
    print(f"  ✓ 신고 {count:,}개")


async def seed_dms(pool: aiomysql.Pool) -> None:
    """DM 대화 ~5,000개 + 메시지 ~75,000개."""
    print(f"  DM 대화 {TOTAL_DM_CONVERSATIONS:,}개 생성 중...")

    # 팔로우 관계에서 대화 쌍 우선 생성 (80%)
    follow_based = int(TOTAL_DM_CONVERSATIONS * 0.8)
    seen_pairs: set[tuple[int, int]] = set()
    conv_pairs: list[tuple[int, int]] = []

    # 팔로우 기반 쌍
    async with pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT follower_id, following_id FROM user_follow ORDER BY RAND() LIMIT %s",
            (follow_based * 2,),
        )
        follow_rows = await cur.fetchall()

    for a, b in follow_rows:
        if len(conv_pairs) >= follow_based:
            break
        p1, p2 = min(a, b), max(a, b)
        if (p1, p2) not in seen_pairs:
            seen_pairs.add((p1, p2))
            conv_pairs.append((p1, p2))

    # 랜덤 쌍으로 나머지 채우기
    attempts = 0
    while len(conv_pairs) < TOTAL_DM_CONVERSATIONS and attempts < TOTAL_DM_CONVERSATIONS * 5:
        a = random.randint(1, TOTAL_USERS)
        b = random.randint(1, TOTAL_USERS)
        if a != b:
            p1, p2 = min(a, b), max(a, b)
            if (p1, p2) not in seen_pairs:
                seen_pairs.add((p1, p2))
                conv_pairs.append((p1, p2))
        attempts += 1

    # 대화 + 메시지 삽입 (배치 500 대화씩)
    total_messages = 0
    CONV_BATCH = 500
    for batch_start in range(0, len(conv_pairs), CONV_BATCH):
        batch = conv_pairs[batch_start : batch_start + CONV_BATCH]
        async with pool.acquire() as conn:
            await conn.begin()
            try:
                async with conn.cursor() as cur:
                    for p1, p2 in batch:
                        created_at = growth_curve_timestamp(60)
                        await cur.execute(
                            "INSERT IGNORE INTO dm_conversation "
                            "(participant1_id, participant2_id, last_message_at, created_at) "
                            "VALUES (%s, %s, %s, %s)",
                            (p1, p2, None, created_at),
                        )
                        conv_id = cur.lastrowid
                        if not conv_id:
                            continue

                        msg_count = random.randint(
                            max(1, DM_MESSAGES_PER_CONV - 5),
                            DM_MESSAGES_PER_CONV + 5,
                        )
                        last_msg_at = created_at
                        for j in range(msg_count):
                            sender = p1 if j % 2 == 0 else p2
                            content = fake.sentence()
                            msg_at = last_msg_at + timedelta(minutes=random.randint(1, 120))
                            is_read = 1 if j < msg_count - 1 else (1 if random.random() < 0.8 else 0)
                            await cur.execute(
                                "INSERT INTO dm_message "
                                "(conversation_id, sender_id, content, is_read, created_at) "
                                "VALUES (%s, %s, %s, %s, %s)",
                                (conv_id, sender, content, is_read, msg_at),
                            )
                            last_msg_at = msg_at
                            total_messages += 1

                        await cur.execute(
                            "UPDATE dm_conversation SET last_message_at = %s WHERE id = %s",
                            (last_msg_at, conv_id),
                        )
                await conn.commit()
            except Exception:
                await conn.rollback()
                raise

        progress(min(batch_start + CONV_BATCH, len(conv_pairs)), len(conv_pairs), "DM 대화")

    print(f"  ✓ DM 대화 {len(conv_pairs):,}개, 메시지 {total_messages:,}개")


# ─────────────────────────────────────────────
# 패키지 + 리뷰
# ─────────────────────────────────────────────

PACKAGES = [
    ("vim", "Vim", "터미널 기반 텍스트 에디터", "https://www.vim.org", "editor", "apt"),
    ("neovim", "Neovim", "Vim 기반 하이퍼 확장 에디터", "https://neovim.io", "editor", "apt"),
    ("docker", "Docker", "컨테이너 플랫폼", "https://www.docker.com", "devtool", "apt"),
    ("git", "Git", "분산 버전 관리 시스템", "https://git-scm.com", "devtool", "apt"),
    ("tmux", "tmux", "터미널 멀티플렉서", "https://github.com/tmux/tmux", "terminal", "apt"),
    ("zsh", "Zsh", "Z 셸", "https://www.zsh.org", "terminal", "apt"),
    ("htop", "htop", "대화형 프로세스 뷰어", "https://htop.dev", "system", "apt"),
    ("fzf", "fzf", "커맨드라인 퍼지 파인더", "https://github.com/junegunn/fzf", "utility", "apt"),
    ("ripgrep", "ripgrep", "초고속 검색 도구", "https://github.com/BurntSushi/ripgrep", "utility", "apt"),
    ("alacritty", "Alacritty", "GPU 가속 터미널 에뮬레이터", "https://alacritty.org", "terminal", "apt"),
    ("nginx", "nginx", "웹 서버 및 리버스 프록시", "https://nginx.org", "system", "apt"),
    ("vlc", "VLC", "멀티미디어 플레이어", "https://www.videolan.org", "multimedia", "apt"),
    ("gimp", "GIMP", "GNU 이미지 편집기", "https://www.gimp.org", "multimedia", "apt"),
    ("ufw", "UFW", "간편 방화벽", "https://launchpad.net/ufw", "security", "apt"),
    ("gnome-shell", "GNOME Shell", "GNOME 데스크톱 환경", "https://www.gnome.org", "desktop", "apt"),
]

REVIEW_TITLES = [
    "최고의 도구입니다",
    "매일 사용하는 필수 프로그램",
    "초보자에게 추천합니다",
    "기대 이하였습니다",
    "대안이 더 나은 것 같아요",
    "설정이 좀 복잡하지만 강력합니다",
    "리눅스 필수 패키지",
    "오래 써본 솔직한 후기",
    "입문용으로 괜찮습니다",
    "프로덕션에서 검증된 도구",
]

REVIEW_CONTENTS = [
    "설치 후 바로 쓸 수 있어서 좋았습니다. 문서도 잘 되어 있고요.",
    "처음에는 러닝 커브가 있지만 익숙해지면 생산성이 확 올라갑니다.",
    "다른 대안도 써봤지만 결국 이걸로 돌아오게 됩니다.",
    "솔직히 기대만큼은 아니었어요. 제 사용 패턴에는 안 맞는 듯합니다.",
    "가볍고 빠릅니다. 리소스 적은 서버에서도 잘 돌아갑니다.",
    "플러그인 생태계가 활발해서 확장성이 좋습니다.",
    "버그가 가끔 있지만 업데이트가 빠릅니다.",
    "UI가 직관적이지 않아서 처음에 헤맸습니다.",
    "오픈소스라서 커스텀이 자유롭고 커뮤니티도 활발합니다.",
    "서버 관리할 때 없으면 안 되는 도구입니다.",
]

TOTAL_PACKAGE_REVIEWS = 10_000

WIKI_PAGES_DATA = [
    (
        "Ubuntu 설치 가이드",
        "ubuntu-install-guide",
        "## Ubuntu 설치 가이드\n\n### USB 부팅 디스크 만들기\n```bash\nsudo dd if=ubuntu-24.04.iso of=/dev/sdX bs=4M status=progress\n```\n\n### 설치 후 필수 작업\n```bash\nsudo apt update && sudo apt upgrade -y\nsudo apt install build-essential curl wget\n```",
        ["ubuntu", "파일시스템"],
    ),
    (
        "Arch Linux 설치 가이드",
        "arch-install-guide",
        "## Arch Linux 수동 설치\n\n```bash\nfdisk /dev/sda\nmkfs.ext4 /dev/sda3\nmount /dev/sda3 /mnt\npacstrap /mnt base linux linux-firmware\ngenfstab -U /mnt >> /mnt/etc/fstab\narch-chroot /mnt\n```\n\n### 자주 빠뜨리는 것\n- `networkmanager` 설치 + `systemctl enable NetworkManager`",
        ["arch", "파일시스템"],
    ),
    (
        "한글 입력기 설정",
        "korean-input-setup",
        "## IBus + 한글 설정\n\n```bash\nsudo apt install ibus-hangul   # Ubuntu\nsudo dnf install ibus-hangul   # Fedora\nsudo pacman -S ibus-hangul     # Arch\n```\n\n환경 변수:\n```bash\nexport GTK_IM_MODULE=ibus\nexport QT_IM_MODULE=ibus\nexport XMODIFIERS=@im=ibus\n```",
        ["ubuntu", "fedora", "arch"],
    ),
    (
        "Windows 듀얼 부팅",
        "dual-boot-windows",
        "## 듀얼 부팅 설정\n\n1. Windows 디스크 축소\n2. Secure Boot 비활성화\n3. Linux 설치 (GRUB이 Windows 자동 감지)\n\n시간 동기화:\n```bash\ntimedatectl set-local-rtc 1\n```",
        ["ubuntu", "파일시스템"],
    ),
    (
        "NVIDIA 드라이버 설치",
        "nvidia-driver-install",
        "## NVIDIA 드라이버\n\n```bash\n# Ubuntu\nsudo ubuntu-drivers autoinstall\n# Fedora\nsudo dnf install akmod-nvidia\n# Arch\nsudo pacman -S nvidia nvidia-utils\n```\n\nSecure Boot 환경:\n```bash\nsudo mokutil --import /var/lib/dkms/mok.pub\n```",
        ["ubuntu", "fedora", "arch"],
    ),
    (
        "SSH 키 생성 및 설정",
        "ssh-key-setup",
        '## SSH 키 인증\n\n```bash\nssh-keygen -t ed25519 -C "your@email.com"\nssh-copy-id user@server-ip\n```\n\n보안 강화 (sshd_config):\n```\nPasswordAuthentication no\nPermitRootLogin no\n```',
        ["ssh", "보안", "서버관리"],
    ),
    (
        "systemd 서비스 만들기",
        "systemd-service-create",
        "## systemd 서비스\n\n```ini\n[Unit]\nDescription=My App\nAfter=network.target\n[Service]\nExecStart=/opt/myapp/start.sh\nRestart=on-failure\n[Install]\nWantedBy=multi-user.target\n```\n\n```bash\nsudo systemctl daemon-reload && sudo systemctl enable myapp\n```",
        ["systemd", "서버관리"],
    ),
    (
        "GRUB 부트로더 복구",
        "grub-recovery",
        "## GRUB 복구\n\nLive USB로 부팅 후:\n```bash\nsudo mount /dev/sda3 /mnt\nsudo mount /dev/sda1 /mnt/boot/efi\nsudo chroot /mnt\ngrub-install --target=x86_64-efi\nupdate-grub\n```",
        ["ubuntu", "arch"],
    ),
    (
        "UFW 방화벽 설정",
        "firewall-ufw-guide",
        "## UFW 방화벽\n\n```bash\nsudo ufw enable\nsudo ufw default deny incoming\nsudo ufw allow 22/tcp\nsudo ufw allow 80,443/tcp\n```\n\n> SSH 포트를 차단하면 원격 접속이 끊깁니다!",
        ["보안", "서버관리"],
    ),
    (
        "Docker 시작하기",
        "docker-getting-started",
        "## Docker 기본\n\n```bash\ncurl -fsSL https://get.docker.com | sh\nsudo usermod -aG docker $USER\n```\n\n```bash\ndocker run -d --name myapp -p 8080:80 nginx\ndocker logs -f myapp\n```",
        ["docker", "서버관리"],
    ),
    (
        "Vim 기본 사용법",
        "vim-basic-usage",
        "## Vim 입문\n\n모드: Normal(`Esc`), Insert(`i`), Visual(`v`), Command(`:`)\n\n```\ndd(줄 삭제), yy(복사), p(붙여넣기), u(취소)\n/pattern (검색), :wq (저장 종료)\n```\n\n> `vimtutor`로 30분 튜토리얼 먼저!",
        ["vim"],
    ),
    (
        "패키지 매니저 비교",
        "package-manager-comparison",
        "## 패키지 매니저\n\n| PM | 배포판 | 예시 |\n|---|---|---|\n| APT | Ubuntu | `apt install vim` |\n| DNF | Fedora | `dnf install vim` |\n| Pacman | Arch | `pacman -S vim` |",
        ["패키지관리", "ubuntu", "fedora", "arch"],
    ),
    (
        "리눅스 디렉토리 구조",
        "linux-directory-structure",
        "## FHS\n\n```\n/bin    필수 바이너리\n/etc    설정 파일\n/home   사용자 홈\n/var    가변 데이터 (로그)\n/proc   프로세스 가상 FS\n/tmp    임시 파일\n```",
        ["파일시스템"],
    ),
    (
        "Cron 작업 스케줄링",
        "cron-job-setup",
        "## Cron\n\n```bash\ncrontab -e\n```\n\n```\n분 시 일 월 요일 명령\n0 2 * * * /home/user/backup.sh\n*/5 * * * * health-check.sh\n```\n\n> cron은 환경 변수를 로드하지 않습니다. 절대 경로 사용하세요.",
        ["서버관리"],
    ),
    (
        "스왑 파티션 설정",
        "swap-partition-setup",
        "## 스왑 파일\n\n```bash\nsudo fallocate -l 4G /swapfile\nsudo chmod 600 /swapfile\nsudo mkswap /swapfile\nsudo swapon /swapfile\necho '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab\n```\n\nSSD는 swappiness를 10~20으로 낮추세요.",
        ["파일시스템", "성능최적화"],
    ),
]


async def seed_packages(pool: aiomysql.Pool) -> None:
    """패키지 15개 삽입."""
    print(f"  패키지 {len(PACKAGES)}개 생성 중...")
    data = [(name, display, desc, url, cat, pm, 1) for name, display, desc, url, cat, pm in PACKAGES]
    count = await batch_insert_raw(
        pool,
        "package",
        ["name", "display_name", "description", "homepage_url", "category", "package_manager", "created_by"],
        data,
        ignore=True,
    )
    print(f"  ✓ 패키지 {count}개")


async def seed_package_reviews(pool: aiomysql.Pool) -> None:
    """패키지 리뷰 ~10,000개 생성 (평점 1~5 균등 분포)."""
    print(f"  패키지 리뷰 {TOTAL_PACKAGE_REVIEWS:,}개 생성 중...")
    num_packages = len(PACKAGES)

    seen: set[tuple[int, int]] = set()
    data: list[tuple] = []
    attempts = 0

    while len(data) < TOTAL_PACKAGE_REVIEWS and attempts < TOTAL_PACKAGE_REVIEWS * 3:
        attempts += 1
        pkg_id = random.randint(1, num_packages)
        user_id = weighted_user_id(0.3, 0.4)
        key = (pkg_id, user_id)
        if key in seen:
            continue
        seen.add(key)
        rating = random.randint(1, 5)
        title = random.choice(REVIEW_TITLES)
        content = random.choice(REVIEW_CONTENTS)
        created_at = growth_curve_timestamp(180)
        data.append((pkg_id, user_id, rating, title, content, created_at))

    count = await batch_insert_raw(
        pool,
        "package_review",
        ["package_id", "user_id", "rating", "title", "content", "created_at"],
        data,
        ignore=True,
    )
    print(f"  ✓ 패키지 리뷰 {count:,}개 (평점 1~5 균등)")


async def seed_wiki_pages(pool: aiomysql.Pool) -> None:
    """FAQ 스타일 위키 페이지 + 태그 연결 생성."""
    n = len(WIKI_PAGES_DATA)
    print(f"  위키 페이지 {n}개 생성 중...")

    conn = await pool.acquire()
    try:
        async with conn.cursor() as cur:
            await cur.execute("BEGIN")
            try:
                for title, slug, content, tag_names in WIKI_PAGES_DATA:
                    author_id = weighted_user_id(0.5, 0.3)
                    views_count = random.randint(50, 5000)
                    created_at = growth_curve_timestamp(180)

                    await cur.execute(
                        "INSERT IGNORE INTO wiki_page (title, slug, content, author_id, views_count, created_at) "
                        "VALUES (%s, %s, %s, %s, %s, %s)",
                        (title, slug, content, author_id, views_count, created_at),
                    )
                    wiki_page_id = cur.lastrowid
                    if not wiki_page_id:
                        continue

                    for tag_name in tag_names:
                        await cur.execute("SELECT id FROM tag WHERE name = %s", (tag_name,))
                        row = await cur.fetchone()
                        if row:
                            await cur.execute(
                                "INSERT IGNORE INTO wiki_page_tag (wiki_page_id, tag_id) VALUES (%s, %s)",
                                (wiki_page_id, row[0]),
                            )

                await cur.execute("COMMIT")
            except Exception:
                await cur.execute("ROLLBACK")
                raise
    finally:
        pool.release(conn)

    print(f"  ✓ 위키 페이지 {n}개 (FAQ, 태그 연결)")


async def seed_notification_settings(pool: aiomysql.Pool) -> None:
    """사용자의 ~20%에 대해 커스텀 알림 설정 생성."""
    n = int(TOTAL_USERS * 0.2)
    print(f"  알림 설정 {n:,}개 생성 중...")

    user_ids = random.sample(range(1, TOTAL_USERS + 1), n)
    data: list[tuple] = []
    for user_id in user_ids:
        # 각 타입별로 20% 확률로 OFF
        settings = [0 if random.random() < 0.2 else 1 for _ in range(5)]
        data.append((user_id, *settings))

    count = await batch_insert_raw(
        pool,
        "notification_setting",
        ["user_id", "comment_enabled", "like_enabled", "mention_enabled", "follow_enabled", "bookmark_enabled"],
        data,
        ignore=True,
    )
    print(f"  ✓ 알림 설정 {count:,}명 (각 타입 ~20% OFF)")


async def verify_data(pool: aiomysql.Pool) -> None:
    """시딩 결과 검증 (테이블별 행 수 + 무결성)."""
    tables = [
        "user",
        "category",
        "tag",
        "post",
        "post_tag",
        "post_image",
        "poll",
        "poll_option",
        "poll_vote",
        "comment",
        "post_like",
        "post_bookmark",
        "comment_like",
        "post_view_log",
        "user_follow",
        "user_block",
        "notification",
        "notification_setting",
        "report",
        "dm_conversation",
        "dm_message",
        "package",
        "package_review",
        "wiki_page",
        "wiki_page_tag",
    ]

    print("  테이블별 행 수:")
    async with pool.acquire() as conn, conn.cursor() as cur:
        for table in tables:
            await cur.execute(f"SELECT COUNT(*) FROM {table}")
            (count,) = await cur.fetchone()
            print(f"    {table:.<25s} {count:>12,}")

        # 무결성 검증 1: 고아 댓글 (parent_id가 존재하지 않는 comment 참조)
        await cur.execute("""
                SELECT COUNT(*) FROM comment c
                WHERE c.parent_id IS NOT NULL
                AND NOT EXISTS (SELECT 1 FROM comment p WHERE p.id = c.parent_id)
            """)
        (orphan_comments,) = await cur.fetchone()
        if orphan_comments:
            print(f"  ⚠ 고아 댓글: {orphan_comments:,}개")
        else:
            print("  ✓ 고아 댓글 없음")

        # 무결성 검증 2: DM 정규화 (participant1_id < participant2_id)
        await cur.execute("""
                SELECT COUNT(*) FROM dm_conversation
                WHERE participant1_id >= participant2_id
            """)
        (bad_dm,) = await cur.fetchone()
        if bad_dm:
            print(f"  ⚠ DM 정규화 위반: {bad_dm:,}개")
        else:
            print("  ✓ DM 정규화 정상")

        # 무결성 검증 3: 대댓글이 1단계만인지 확인
        await cur.execute("""
                SELECT COUNT(*) FROM comment c
                JOIN comment p ON c.parent_id = p.id
                WHERE p.parent_id IS NOT NULL
            """)
        (nested_replies,) = await cur.fetchone()
        if nested_replies:
            print(f"  ⚠ 2단계 이상 대댓글: {nested_replies:,}개")
        else:
            print("  ✓ 대댓글 1단계만 존재")


async def trigger_recompute(url: str) -> None:
    """추천 피드 점수 재계산 API 호출."""
    print(f"\n  추천 피드 재계산: {url}/v1/admin/feed/recompute")

    try:
        import json
        import urllib.request

        # admin 로그인
        login_data = json.dumps(
            {
                "email": "user1@example.com",
                "password": "Test1234!",
            }
        ).encode()
        login_req = urllib.request.Request(
            f"{url}/v1/auth/login",
            data=login_data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(login_req, timeout=30) as resp:
            token_data = json.loads(resp.read())
            access_token = token_data["access_token"]

        # 재계산 호출 (대규모 데이터라 타임아웃 넉넉하게)
        recompute_req = urllib.request.Request(
            f"{url}/v1/admin/feed/recompute",
            headers={"Authorization": f"Bearer {access_token}"},
            method="POST",
        )
        with urllib.request.urlopen(recompute_req, timeout=600) as resp:
            result = json.loads(resp.read())
            print(f"  ✓ 재계산 완료: {result}")

    except Exception as e:
        print(f"  ⚠ 재계산 실패: {e}")
        print(f"  수동 실행: curl -X POST {url}/v1/admin/feed/recompute -H 'Authorization: Bearer <token>'")


# ─────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────


async def main() -> None:
    """대규모 시드 데이터 생성 메인 함수."""
    args = parse_args()

    # 배너 출력
    print("=" * 60)
    print("  대규모 시드 데이터 생성")
    print("=" * 60)
    print(f"  대상 DB: {args.db_user}@{args.db_host}:{args.db_port}/{args.db_name}")
    print(f"  옵션: clean={args.clean}, dry_run={args.dry_run}")
    print("-" * 60)
    print(f"  사용자: {TOTAL_USERS:>10,}명")
    print(f"    - Power  ({POWER_RATIO:.0%}): {POWER_COUNT:>10,}명")
    print(f"    - Regular({REGULAR_RATIO:.0%}): {REGULAR_COUNT:>10,}명")
    print(f"    - Reader ({READER_RATIO:.0%}): {READER_COUNT:>10,}명")
    print(f"  배치 크기: {BATCH_SIZE:,}")
    print("=" * 60)

    # Dry-run 모드: 설정만 확인하고 종료
    if args.dry_run:
        print("\n[dry-run] DB 접속 없이 종료합니다.")
        return

    # 확인 프롬프트
    if not args.no_confirm:
        confirm = input("\n시딩을 시작할까요? (yes/no): ")
        if confirm.lower() != "yes":
            print("취소되었습니다.")
            return

    # DB 연결
    pool = await create_pool(args)
    start_time = time.time()

    try:
        # 기존 데이터 카운트 확인
        async with pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute("SELECT COUNT(*) FROM user")
            (user_count,) = await cur.fetchone()
            print(f"\n현재 user 테이블: {user_count:,}행")

        # 기존 데이터 삭제
        if args.clean:
            print("\n[Phase 0] 기존 데이터 삭제")
            await clean_all_data(pool)

        # Phase 1: 기초 데이터 (순차 — FK 의존성)
        print("\n[Phase 1] 기초 데이터: 사용자, 카테고리, 태그, 패키지")
        await seed_users(pool)
        await seed_categories(pool)
        await seed_tags(pool)
        await seed_packages(pool)

        # Phase 2: 게시글 관련 (순차 — post_id FK 의존)
        print("\n[Phase 2] 게시글 관련: 게시글, 태그 연결, 이미지, 투표, 위키")
        await seed_posts(pool)
        await seed_post_tags(pool)
        await seed_post_images(pool)
        await seed_polls(pool)
        await seed_wiki_pages(pool)

        # Phase 3: 게시글/댓글 인터랙션 (병렬 — 서로 독립)
        print("\n[Phase 3] 인터랙션: 댓글, 좋아요, 북마크, 조회, 패키지 리뷰")
        await seed_comments(pool)  # 댓글은 먼저 (comment_likes가 의존)
        await asyncio.gather(
            seed_post_likes(pool),
            seed_bookmarks(pool),
            seed_comment_likes(pool),
            seed_view_logs(pool),
            seed_poll_votes(pool),
            seed_package_reviews(pool),
        )

        # Phase 4: 소셜/기타 (병렬 — 서로 독립)
        print("\n[Phase 4] 소셜: 팔로우, 차단, 알림, 신고, DM, 알림 설정")
        await asyncio.gather(
            seed_follows(pool),
            seed_blocks(pool),
            seed_notifications(pool),
            seed_notification_settings(pool),
            seed_reports(pool),
            seed_dms(pool),
        )

        # Phase 5: 검증 + 추천 피드 재계산
        print("\n[Phase 5] 검증 및 후처리")
        await verify_data(pool)

        if args.recompute_url:
            await trigger_recompute(args.recompute_url)

        # 완료 요약
        elapsed = time.time() - start_time
        minutes = int(elapsed // 60)
        seconds = elapsed % 60
        print("\n" + "=" * 60)
        print(f"  시딩 완료! 소요 시간: {minutes}분 {seconds:.1f}초")
        print("=" * 60)
        print("  로그인 정보:")
        print("    - admin: user1@example.com / Test1234!")
        print(f"    - 일반: user2@example.com ~ user{TOTAL_USERS}@example.com / Test1234!")
        print("=" * 60)

    finally:
        pool.close()
        await pool.wait_closed()
        print("DB 커넥션 풀 종료")


if __name__ == "__main__":
    asyncio.run(main())
