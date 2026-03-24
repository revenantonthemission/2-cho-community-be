"""seed_data.py: 개발/테스트용 더미 데이터 생성 스크립트.

사용법:
    source .venv/bin/activate
    python core/database/seed_data.py [--scale small|medium|large]

생성되는 데이터 (small 기준):
    - 50 users (이메일 인증 완료, admin 1명, distro 분포 포함)
    - 15 packages + 100 reviews (평점 1~5 균등)
    - 200 posts (리눅스 마크다운 콘텐츠, 카테고리, 태그)
    - 800 comments (대댓글 20%)
    - 500 post_likes, 200 bookmarks, 300 comment_likes
    - 100 follows, 10 blocks
    - 30 tags, 20 polls, 100 notifications
    - 15 reports, 300 view_logs
    - 15 wiki pages (FAQ, 태그 연결)
    - 10 notification_settings (커스텀)
    - 10 DM conversations with ~50 messages
"""

import argparse
import asyncio
import random

# 프로젝트 루트를 PYTHONPATH에 추가
import sys
from datetime import datetime, timedelta
from pathlib import Path

from faker import Faker

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database.connection import close_db, init_db, transactional
from core.utils.password import hash_password

fake = Faker("ko_KR")
Faker.seed(42)  # 재현 가능한 데이터
random.seed(42)

# 규모 프리셋
SCALE_PRESETS = {
    "small": {
        "users": 50,
        "posts": 200,
        "comments": 800,
        "post_likes": 500,
        "bookmarks": 200,
        "comment_likes": 300,
        "follows": 100,
        "blocks": 10,
        "tags": 30,
        "polls": 20,
        "notifications": 100,
        "reports": 15,
        "view_logs": 300,
        "dm_conversations": 10,
        "dm_messages_per_conv": 5,
        "wiki_pages": 15,
        "package_reviews": 100,
        "notification_settings": 10,
    },
    "medium": {
        "users": 500,
        "posts": 2000,
        "comments": 8000,
        "post_likes": 5000,
        "bookmarks": 2000,
        "comment_likes": 3000,
        "follows": 1000,
        "blocks": 50,
        "tags": 30,
        "polls": 100,
        "notifications": 1000,
        "reports": 100,
        "view_logs": 5000,
        "dm_conversations": 50,
        "dm_messages_per_conv": 10,
        "wiki_pages": 15,
        "package_reviews": 500,
        "notification_settings": 100,
    },
    "large": {
        "users": 10000,
        "posts": 50000,
        "comments": 200000,
        "post_likes": 100000,
        "bookmarks": 30000,
        "comment_likes": 50000,
        "follows": 20000,
        "blocks": 500,
        "tags": 30,
        "polls": 500,
        "notifications": 10000,
        "reports": 500,
        "view_logs": 100000,
        "dm_conversations": 500,
        "dm_messages_per_conv": 15,
        "wiki_pages": 15,
        "package_reviews": 5000,
        "notification_settings": 2000,
    },
}

# 미리 해시된 비밀번호 (Test1234!)
HASHED_PASSWORD = hash_password("Test1234!")

# 배포판 분포 (Camp Linux 테마)
DISTROS = ["ubuntu", "fedora", "arch", "debian", "mint", "opensuse", "manjaro", "other", None]
DISTRO_WEIGHTS = [0.30, 0.15, 0.15, 0.12, 0.08, 0.05, 0.05, 0.05, 0.05]

# ─────────────────────────────────────────────
# 리눅스 테마 콘텐츠
# ─────────────────────────────────────────────

MARKDOWN_CONTENTS = [
    """## Ubuntu 24.04 LTS 업그레이드 후기

드디어 Noble Numbat으로 업그레이드했습니다.

### 달라진 점
- **GNOME 46** — 파일 관리자 속도 체감
- **Linux Kernel 6.8** — 하드웨어 호환성 개선
- **APT 변경사항** — `apt`가 더 빨라진 느낌

### 업그레이드 과정
```bash
sudo apt update && sudo apt full-upgrade
sudo do-release-upgrade
```

> 클린 설치보다 업그레이드가 편하긴 한데, 기존 PPA 충돌만 조심하세요!""",
    """Arch Linux를 메인으로 쓴 지 1년이 됐습니다.

**Rolling Release**의 장단점을 체감하고 있습니다.

| 항목 | 장점 | 단점 |
|------|------|------|
| 패키지 | 항상 최신 | 가끔 깨짐 |
| 커스텀 | 완전한 자유 | 직접 해야 함 |
| 문서 | Arch Wiki 최강 | 러닝 커브 높음 |

특히 `pacman -Syu` 한 방이면 전체 시스템이 최신 상태가 되는 게 매력입니다.""",
    """### i3wm 타일링 윈도우 매니저 설정 공유

데스크톱 환경 없이 i3wm만 쓰고 있습니다.

1. **i3-gaps** — 창 사이 간격 설정
2. **polybar** — 상태 바 커스텀
3. **rofi** — 앱 런처
4. **picom** — 컴포지터 (투명도, 그림자)

```bash
# i3 설정 파일 위치
~/.config/i3/config

# 자주 쓰는 키바인딩
bindsym $mod+Return exec alacritty
bindsym $mod+d exec rofi -show drun
bindsym $mod+Shift+q kill
```

미니멀한 작업 환경을 원하시면 추천합니다!""",
    """## systemd 서비스 직접 만들기

커스텀 데몬을 systemd로 관리하는 방법입니다.

### 서비스 파일 생성
```ini
# /etc/systemd/system/myapp.service
[Unit]
Description=My Application
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/myapp
ExecStart=/opt/myapp/run.sh
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 주요 명령어
```bash
sudo systemctl daemon-reload
sudo systemctl enable myapp
sudo systemctl start myapp
journalctl -u myapp -f  # 로그 실시간 확인
```

> `Restart=on-failure`와 `RestartSec`을 꼭 설정하세요. 크래시 루프 방지에 필수입니다.""",
    """NVIDIA 드라이버 삽질기를 공유합니다.

### 증상
Ubuntu에서 `nvidia-smi` 실행 시 `No devices were found` 에러.

### 원인 분석
1. `lspci | grep -i nvidia` → GPU 인식은 됨
2. `dmesg | grep -i nvidia` → 모듈 로드 실패
3. Secure Boot가 서명되지 않은 커널 모듈 차단!

### 해결
```bash
# 방법 1: Secure Boot 비활성화 (BIOS)
# 방법 2: MOK 등록 (권장)
sudo mokutil --import /var/lib/dkms/mok.pub
# 재부팅 후 MOK Manager에서 Enroll 선택
```

인덱스 하나로 5초 → 50ms 개선이 아니라, Secure Boot 하나로 3일 삽질이었습니다.""",
    """프론트엔드 개발할 때 WSL2 + Docker 조합이 편합니다.

- **WSL2 Ubuntu** 안에서 개발 서버 실행
- **Docker Desktop** WSL2 백엔드 모드 사용
- VS Code **Remote - WSL** 확장으로 리눅스 파일시스템 직접 편집
- `localhost` 포워딩 자동 지원

```bash
# WSL에서 Docker 상태 확인
docker info | grep "Operating System"
# Output: Docker Desktop (WSL2 backend)
```

Windows 파일시스템(`/mnt/c/`)에서 작업하면 느리니 반드시 `~/` 아래에서 작업하세요.""",
    """## 내 dotfiles 관리 방법

bare Git repo로 dotfiles를 관리하고 있습니다.

### 초기 설정
```bash
git init --bare $HOME/.dotfiles
alias dotgit='git --git-dir=$HOME/.dotfiles --work-tree=$HOME'
dotgit config --local status.showUntrackedFiles no
```

### 사용법
```bash
dotgit add ~/.bashrc ~/.config/i3/config
dotgit commit -m "i3 키바인딩 업데이트"
dotgit push origin main
```

### 새 머신에서 복원
```bash
git clone --bare <repo-url> $HOME/.dotfiles
dotgit checkout
```

Stow나 chezmoi보다 간단하고, 별도 도구 설치가 필요 없어서 좋습니다.""",
    """취업 준비하면서 정리한 **리눅스 면접 필수 개념**입니다.

### 프로세스 관리
- `fork()` vs `exec()` vs `clone()`
- 좀비 프로세스와 고아 프로세스
- 시그널 핸들링 (SIGTERM vs SIGKILL)

### 파일 시스템
- inode 구조, 하드링크 vs 심볼릭링크
- `/proc`, `/sys` 가상 파일시스템
- 파일 퍼미션 비트 (setuid, sticky bit)

### 네트워크
- iptables/nftables 규칙 구조
- TCP 3-way handshake, TIME_WAIT
- `ss` vs `netstat` (ss가 더 빠름)

### 기출 질문
~~"리눅스에서 부팅 과정을 설명하세요"~~ → BIOS/UEFI → GRUB → Kernel → init/systemd

이 정도만 기억해도 시스템 엔지니어 면접 기본은 합니다.""",
]

PLAIN_CONTENTS = [
    "오늘 커널 업데이트 후 부팅이 안 돼서 GRUB에서 이전 커널로 복구했습니다. 여러분도 커널 업데이트 전에 스냅샷 꼭 남기세요.",
    "Fedora 40에서 Wayland가 기본이 됐는데, X11 전용 앱들이 XWayland로 잘 돌아가더라고요. 체감 차이는 거의 없었습니다.",
    "리눅스 민트에서 우분투로 갈아탔는데, Cinnamon이 그립습니다. GNOME은 확장 없이는 좀 불편하네요.",
    "ZFS on Linux 써보신 분? 스냅샷이랑 압축이 좋다는데 메모리를 많이 먹는다고 해서 고민됩니다.",
    "오늘 처음으로 Arch 설치에 성공했습니다! archinstall 안 쓰고 수동으로 했는데 뿌듯하네요.",
    "서버 관리할 때 Ansible이랑 셸 스크립트 중에 뭐가 나을까요? 서버 5대 정도 규모입니다.",
    "tmux 설정 공유합니다. prefix를 Ctrl+a로 바꾸고 마우스 모드 켜면 훨씬 편합니다.",
    "Flatpak vs Snap 논쟁이 다시 시작됐네요. 개인적으로 Flatpak이 더 가볍게 느껴집니다.",
]

TITLES = [
    "Ubuntu 24.04 업그레이드 후기",
    "Arch Linux 설치 삽질기",
    "Fedora에서 Wayland 사용 경험",
    "NVIDIA 드라이버 설치 가이드",
    "i3wm 설정 공유합니다",
    "systemd 서비스 만들기",
    "내 dotfiles 공유",
    "리눅스 면접 준비 정리",
    "커널 패닉 복구 방법",
    "ZFS vs Btrfs 비교",
    "WSL2 개발 환경 세팅",
    "SSH 터널링 활용법",
    "Vim 플러그인 추천",
    "Docker 컨테이너 경량화 팁",
    "리눅스 보안 강화 체크리스트",
    "GRUB 커스텀 테마 적용",
    "Flatpak vs Snap 비교",
    "tmux 설정 공유",
    "Ansible로 서버 관리하기",
    "리눅스 데스크톱 쇼케이스",
]

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
]

TAG_NAMES = [
    "ubuntu",
    "fedora",
    "arch",
    "debian",
    "mint",
    "kernel",
    "systemd",
    "wayland",
    "xorg",
    "gnome",
    "kde",
    "i3wm",
    "docker",
    "vim",
    "neovim",
    "bash",
    "zsh",
    "ssh",
    "nginx",
    "apache",
    "보안",
    "네트워크",
    "파일시스템",
    "패키지관리",
    "dotfiles",
    "서버관리",
    "가상화",
    "백업",
    "모니터링",
    "성능최적화",
]

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
]

REPORT_REASONS = ["spam", "abuse", "inappropriate", "other"]

# 패키지 시드 데이터
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

# 패키지 리뷰 템플릿
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

# 위키 FAQ 데이터
WIKI_PAGES_DATA = [
    (
        "Ubuntu 설치 가이드",
        "ubuntu-install-guide",
        """## Ubuntu 설치 가이드

### USB 부팅 디스크 만들기

```bash
# balenaEtcher 또는 dd 명령 사용
sudo dd if=ubuntu-24.04-desktop-amd64.iso of=/dev/sdX bs=4M status=progress
```

### 설치 과정
1. USB로 부팅 → "Install Ubuntu" 선택
2. 언어, 키보드 레이아웃 선택
3. 디스크 파티션 설정 (자동 또는 수동)
4. 사용자 계정 생성
5. 설치 완료 후 재부팅

### 설치 후 필수 작업
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install build-essential curl wget
```

> **팁**: 듀얼 부팅 시 Windows를 먼저 설치한 후 Ubuntu를 설치하세요.""",
        ["ubuntu", "파일시스템"],
    ),
    (
        "Arch Linux 설치 가이드",
        "arch-install-guide",
        """## Arch Linux 수동 설치

### 사전 준비
- USB 부팅 미디어 준비
- 유선 인터넷 연결 권장 (`ip link`로 확인)

### 핵심 단계
```bash
# 1. 파티션 (UEFI 예시)
fdisk /dev/sda
# EFI: 512M, swap: RAM 크기, root: 나머지

# 2. 포맷 및 마운트
mkfs.fat -F32 /dev/sda1
mkswap /dev/sda2 && swapon /dev/sda2
mkfs.ext4 /dev/sda3
mount /dev/sda3 /mnt

# 3. 기본 시스템 설치
pacstrap /mnt base linux linux-firmware

# 4. fstab 생성
genfstab -U /mnt >> /mnt/etc/fstab

# 5. chroot 진입
arch-chroot /mnt
```

### 자주 빠뜨리는 것
- `networkmanager` 설치 + `systemctl enable NetworkManager`
- 부트로더 (`grub` 또는 `systemd-boot`) 설치""",
        ["arch", "파일시스템"],
    ),
    (
        "한글 입력기 설정",
        "korean-input-setup",
        """## 리눅스 한글 입력 설정 (IBus + 한글)

### 패키지 설치
```bash
# Ubuntu/Debian
sudo apt install ibus-hangul

# Fedora
sudo dnf install ibus-hangul

# Arch
sudo pacman -S ibus-hangul
```

### 환경 변수 설정
`~/.profile` 또는 `~/.xprofile`에 추가:
```bash
export GTK_IM_MODULE=ibus
export QT_IM_MODULE=ibus
export XMODIFIERS=@im=ibus
ibus-daemon -drx
```

### IBus 설정
1. `ibus-setup` 실행
2. Input Method → Add → Korean → Hangul
3. 한영 전환 키: `Hangul` 또는 `Shift+Space`

> **Wayland 사용자**: GNOME Settings → Keyboard → Input Sources에서 추가하세요.""",
        ["ubuntu", "fedora", "arch"],
    ),
    (
        "Windows 듀얼 부팅 설정",
        "dual-boot-windows",
        """## Windows + Linux 듀얼 부팅

### 준비 사항
1. Windows에서 디스크 축소 (디스크 관리 → 볼륨 축소)
2. Secure Boot 비활성화 (BIOS 설정)
3. Fast Startup 비활성화 (Windows 전원 옵션)

### 설치 순서
Windows 먼저 → Linux 나중 (GRUB이 Windows를 자동 감지)

### GRUB에서 Windows 부팅 항목 없을 때
```bash
sudo os-prober
sudo update-grub
```

### 시간 동기화 문제
Windows는 로컬 시간, Linux는 UTC 사용 → 시간이 어긋남:
```bash
# Linux에서 로컬 시간 사용하도록 변경
timedatectl set-local-rtc 1
```""",
        ["ubuntu", "파일시스템"],
    ),
    (
        "NVIDIA 드라이버 설치",
        "nvidia-driver-install",
        """## NVIDIA 드라이버 설치 가이드

### Ubuntu
```bash
# 추천 드라이버 확인
ubuntu-drivers devices

# 자동 설치 (권장)
sudo ubuntu-drivers autoinstall

# 또는 특정 버전 설치
sudo apt install nvidia-driver-550
```

### Fedora
```bash
# RPM Fusion 저장소 추가 필요
sudo dnf install akmod-nvidia
```

### Arch
```bash
sudo pacman -S nvidia nvidia-utils
```

### Secure Boot 환경
드라이버 설치 후 부팅 실패 시 MOK 등록 필요:
```bash
sudo mokutil --import /var/lib/dkms/mok.pub
# 재부팅 → MOK Manager → Enroll MOK
```

### 확인
```bash
nvidia-smi
# GPU 정보와 드라이버 버전이 표시되면 성공
```""",
        ["ubuntu", "fedora", "arch"],
    ),
    (
        "SSH 키 생성 및 설정",
        "ssh-key-setup",
        """## SSH 키 인증 설정

### 키 생성
```bash
ssh-keygen -t ed25519 -C "your@email.com"
# 기본 경로: ~/.ssh/id_ed25519
```

### 서버에 공개키 복사
```bash
ssh-copy-id user@server-ip
# 또는 수동으로
cat ~/.ssh/id_ed25519.pub | ssh user@server-ip "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"
```

### SSH 설정 파일 (~/.ssh/config)
```
Host myserver
    HostName 192.168.1.100
    User admin
    IdentityFile ~/.ssh/id_ed25519
    Port 22
```

### 보안 강화 (서버측 /etc/ssh/sshd_config)
```
PasswordAuthentication no
PermitRootLogin no
PubkeyAuthentication yes
```

> **중요**: `PasswordAuthentication no` 설정 전에 키 인증이 동작하는지 반드시 확인하세요.""",
        ["ssh", "보안", "서버관리"],
    ),
    (
        "systemd 서비스 만들기",
        "systemd-service-create",
        """## 커스텀 systemd 서비스 작성법

### 서비스 파일 위치
- 시스템 서비스: `/etc/systemd/system/`
- 사용자 서비스: `~/.config/systemd/user/`

### 기본 템플릿
```ini
[Unit]
Description=My Application
After=network.target

[Service]
Type=simple
User=appuser
WorkingDirectory=/opt/myapp
ExecStart=/opt/myapp/start.sh
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 주요 명령어
```bash
sudo systemctl daemon-reload    # 파일 변경 후 필수
sudo systemctl enable myapp     # 부팅 시 자동 시작
sudo systemctl start myapp
sudo systemctl status myapp
journalctl -u myapp -f          # 실시간 로그
```""",
        ["systemd", "서버관리"],
    ),
    (
        "GRUB 부트로더 복구",
        "grub-recovery",
        """## GRUB 복구 가이드

### 증상
- 부팅 시 `grub rescue>` 프롬프트
- "no such partition" 에러
- Windows 업데이트 후 GRUB 사라짐

### Live USB로 복구
```bash
# 1. Live USB 부팅 후 파티션 확인
sudo fdisk -l

# 2. 루트 파티션 마운트
sudo mount /dev/sda3 /mnt
sudo mount /dev/sda1 /mnt/boot/efi  # UEFI인 경우

# 3. chroot 진입
sudo mount --bind /dev /mnt/dev
sudo mount --bind /proc /mnt/proc
sudo mount --bind /sys /mnt/sys
sudo chroot /mnt

# 4. GRUB 재설치
grub-install --target=x86_64-efi --efi-directory=/boot/efi
update-grub

# 5. chroot 탈출 및 재부팅
exit
sudo umount -R /mnt
reboot
```""",
        ["ubuntu", "arch"],
    ),
    (
        "UFW 방화벽 설정",
        "firewall-ufw-guide",
        """## UFW 방화벽 설정 가이드

### 기본 사용법
```bash
sudo ufw enable               # 활성화
sudo ufw status verbose        # 상태 확인
sudo ufw default deny incoming # 기본 정책: 수신 차단
sudo ufw default allow outgoing
```

### 포트 허용
```bash
sudo ufw allow 22/tcp          # SSH
sudo ufw allow 80,443/tcp      # HTTP/HTTPS
sudo ufw allow from 192.168.1.0/24  # 특정 서브넷
```

### 규칙 삭제
```bash
sudo ufw status numbered
sudo ufw delete 3              # 번호로 삭제
```

> **주의**: SSH 포트(22)를 차단하면 원격 접속이 끊깁니다. 반드시 SSH 허용 후 활성화하세요.""",
        ["보안", "서버관리"],
    ),
    (
        "Docker 시작하기",
        "docker-getting-started",
        """## Docker 기본 사용법

### 설치 (Ubuntu)
```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# 로그아웃 후 재로그인
```

### 핵심 명령어
```bash
docker run -d --name myapp -p 8080:80 nginx
docker ps                  # 실행 중인 컨테이너
docker logs -f myapp       # 로그 확인
docker exec -it myapp bash # 컨테이너 진입
docker stop myapp && docker rm myapp
```

### Dockerfile 예시
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```

### Docker Compose
```yaml
services:
  web:
    build: .
    ports:
      - "8080:8000"
  db:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: secret
```""",
        ["docker", "서버관리"],
    ),
    (
        "Vim 기본 사용법",
        "vim-basic-usage",
        """## Vim 입문 가이드

### 모드
- **Normal**: 이동 + 명령 (기본)
- **Insert**: `i`, `a`, `o`로 진입, `Esc`로 탈출
- **Visual**: `v`(문자), `V`(줄), `Ctrl+v`(블록)
- **Command**: `:`로 진입

### 필수 명령어
```
이동: h(←) j(↓) k(↑) l(→), w(단어), gg(처음), G(끝)
편집: dd(줄 삭제), yy(줄 복사), p(붙여넣기), u(실행취소)
검색: /pattern, n(다음), N(이전)
저장: :w, :q, :wq, :q!(강제 종료)
```

### .vimrc 기본 설정
```vim
set number          " 줄 번호
set relativenumber  " 상대 줄 번호
set tabstop=4       " 탭 너비
set expandtab       " 탭 → 스페이스
set hlsearch        " 검색 하이라이트
syntax on
```

> **팁**: `vimtutor` 명령으로 30분짜리 튜토리얼을 먼저 해보세요.""",
        ["vim"],
    ),
    (
        "패키지 매니저 비교",
        "package-manager-comparison",
        """## 리눅스 패키지 매니저 비교

| 패키지 매니저 | 배포판 | 명령 예시 |
|------------|--------|---------|
| APT | Ubuntu, Debian | `apt install vim` |
| DNF | Fedora, RHEL | `dnf install vim` |
| Pacman | Arch, Manjaro | `pacman -S vim` |
| Zypper | openSUSE | `zypper install vim` |

### 자주 쓰는 작업 비교

| 작업 | APT | DNF | Pacman |
|------|-----|-----|--------|
| 업데이트 | `apt update` | `dnf check-update` | `pacman -Sy` |
| 업그레이드 | `apt upgrade` | `dnf upgrade` | `pacman -Syu` |
| 검색 | `apt search` | `dnf search` | `pacman -Ss` |
| 삭제 | `apt remove` | `dnf remove` | `pacman -R` |
| 정보 | `apt show` | `dnf info` | `pacman -Si` |

### 범용 패키지 형식
- **Flatpak**: 샌드박스, GNOME 생태계
- **Snap**: Canonical, 자동 업데이트
- **AppImage**: 설치 불필요, 단일 파일""",
        ["패키지관리", "ubuntu", "fedora", "arch"],
    ),
    (
        "리눅스 디렉토리 구조",
        "linux-directory-structure",
        """## FHS (Filesystem Hierarchy Standard)

```
/
├── bin/    → 필수 바이너리 (ls, cp, mv)
├── boot/  → 부트로더, 커널 이미지
├── dev/   → 디바이스 파일 (/dev/sda, /dev/null)
├── etc/   → 시스템 설정 파일
├── home/  → 사용자 홈 디렉토리
├── lib/   → 공유 라이브러리
├── mnt/   → 임시 마운트 포인트
├── opt/   → 서드파티 소프트웨어
├── proc/  → 프로세스 가상 파일시스템
├── root/  → root 사용자 홈
├── sys/   → 커널/하드웨어 가상 파일시스템
├── tmp/   → 임시 파일 (재부팅 시 삭제)
├── usr/   → 사용자 프로그램, 라이브러리
└── var/   → 가변 데이터 (로그, 캐시, DB)
```

### 자주 쓰는 경로
- `/etc/fstab` — 마운트 테이블
- `/var/log/syslog` — 시스템 로그
- `/proc/cpuinfo` — CPU 정보
- `/sys/class/net/` — 네트워크 인터페이스""",
        ["파일시스템"],
    ),
    (
        "Cron 작업 스케줄링",
        "cron-job-setup",
        """## Cron 사용법

### crontab 편집
```bash
crontab -e    # 현재 사용자
sudo crontab -e  # root
```

### 형식
```
분  시  일  월  요일  명령
*   *   *   *   *     command

# 예시
0 2 * * * /home/user/backup.sh        # 매일 02:00
*/5 * * * * /usr/bin/health-check.sh   # 5분마다
0 0 * * 0 apt update && apt upgrade -y # 매주 일요일 자정
```

### 특수 키워드
```
@reboot    # 부팅 시 1회
@hourly    # 매시간 (= 0 * * * *)
@daily     # 매일 (= 0 0 * * *)
@weekly    # 매주
@monthly   # 매월
```

### 로그 확인
```bash
grep CRON /var/log/syslog
```

> **주의**: cron은 사용자 환경 변수를 로드하지 않습니다. 스크립트에서 절대 경로를 사용하세요.""",
        ["서버관리"],
    ),
    (
        "스왑 파티션 설정",
        "swap-partition-setup",
        """## 스왑 설정 가이드

### 스왑 파일 생성 (파티션 없이)
```bash
# 4GB 스왑 파일 생성
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# 영구 설정 (/etc/fstab에 추가)
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### 스왑 크기 권장
| RAM | 스왑 (절전 미사용) | 스왑 (절전 사용) |
|-----|-------------------|----------------|
| 2GB | 2GB | 4GB |
| 8GB | 4GB | 12GB |
| 16GB+ | 4~8GB | RAM + 2GB |

### Swappiness 조정
```bash
# 현재 값 확인 (기본 60)
cat /proc/sys/vm/swappiness

# SSD에서는 낮추는 것이 권장 (10~20)
sudo sysctl vm.swappiness=10
# 영구 적용
echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.conf
```""",
        ["파일시스템", "성능최적화"],
    ),
]


def _random_past(max_days: int = 90) -> datetime:
    """과거 랜덤 시각 생성."""
    return datetime.now() - timedelta(
        days=random.randint(1, max_days),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
    )


def _unique_pairs(n: int, max_a: int, max_b: int, exclude_same: bool = False) -> list[tuple[int, int]]:
    """중복 없는 (a, b) 쌍 생성."""
    seen: set[tuple[int, int]] = set()
    attempts = 0
    max_attempts = n * 5
    while len(seen) < n and attempts < max_attempts:
        a = random.randint(1, max_a)
        b = random.randint(1, max_b)
        if exclude_same and a == b:
            attempts += 1
            continue
        if (a, b) not in seen:
            seen.add((a, b))
        attempts += 1
    return list(seen)


# ─────────────────────────────────────────────
# 데이터 초기화
# ─────────────────────────────────────────────


async def clear_existing_data():
    """기존 데이터 삭제 (개발 환경 전용)."""
    print("기존 데이터 삭제 중...")
    async with transactional() as cur:
        await cur.execute("SET FOREIGN_KEY_CHECKS = 0")
        # 추천 피드
        await cur.execute("TRUNCATE TABLE user_post_score")
        # 위키
        await cur.execute("TRUNCATE TABLE wiki_page_tag")
        await cur.execute("TRUNCATE TABLE wiki_page")
        # 패키지
        await cur.execute("TRUNCATE TABLE package_review")
        await cur.execute("TRUNCATE TABLE package")
        # DM
        await cur.execute("TRUNCATE TABLE dm_message")
        await cur.execute("TRUNCATE TABLE dm_conversation")
        # 투표
        await cur.execute("TRUNCATE TABLE poll_vote")
        await cur.execute("TRUNCATE TABLE poll_option")
        await cur.execute("TRUNCATE TABLE poll")
        # 태그
        await cur.execute("TRUNCATE TABLE post_tag")
        await cur.execute("TRUNCATE TABLE tag")
        # 소셜
        await cur.execute("TRUNCATE TABLE user_follow")
        await cur.execute("TRUNCATE TABLE user_block")
        await cur.execute("TRUNCATE TABLE comment_like")
        await cur.execute("TRUNCATE TABLE post_bookmark")
        # 콘텐츠
        await cur.execute("TRUNCATE TABLE post_image")
        await cur.execute("TRUNCATE TABLE notification_setting")
        await cur.execute("TRUNCATE TABLE notification")
        await cur.execute("TRUNCATE TABLE report")
        await cur.execute("TRUNCATE TABLE post_view_log")
        await cur.execute("TRUNCATE TABLE post_like")
        await cur.execute("TRUNCATE TABLE comment")
        await cur.execute("TRUNCATE TABLE post_draft")
        await cur.execute("TRUNCATE TABLE post")
        # 인증
        await cur.execute("TRUNCATE TABLE social_account")
        await cur.execute("TRUNCATE TABLE email_verification")
        await cur.execute("TRUNCATE TABLE refresh_token")
        await cur.execute("TRUNCATE TABLE image")
        await cur.execute("TRUNCATE TABLE category")
        await cur.execute("TRUNCATE TABLE user")
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
    print("✓ 기존 데이터 삭제 완료")


# ─────────────────────────────────────────────
# 사용자
# ─────────────────────────────────────────────


async def seed_users(cfg: dict):
    """사용자 데이터 생성 (이메일 인증 완료, distro 분포 포함)."""
    n = cfg["users"]
    print(f"사용자 {n}명 생성 중...")

    distro_pool = random.choices(DISTROS, weights=DISTRO_WEIGHTS, k=n)

    users_data = []
    for i in range(1, n + 1):
        email = f"user{i}@example.com"
        nickname = f"user_{i:05d}"
        role = "admin" if i == 1 else "user"
        distro = distro_pool[i - 1]
        created_at = _random_past(365)
        users_data.append((email, 1, nickname, 1, HASHED_PASSWORD, None, role, distro, created_at, created_at))

    async with transactional() as cur:
        await cur.executemany(
            """INSERT INTO user
            (email, email_verified, nickname, nickname_set, password, profile_img, role, distro, created_at, terms_agreed_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            users_data,
        )
    print(f"  ✓ 사용자 {n}명 (admin: user1, 비밀번호: Test1234!)")


# ─────────────────────────────────────────────
# 게시글
# ─────────────────────────────────────────────


async def seed_posts(cfg: dict):
    """게시글 데이터 생성 (리눅스 마크다운 콘텐츠 포함)."""
    n = cfg["posts"]
    print(f"게시글 {n}개 생성 중...")

    posts_data = []
    for i in range(1, n + 1):
        author_id = random.randint(1, cfg["users"])
        title = f"{random.choice(TITLES)} #{i}"

        # 30% 확률로 마크다운 콘텐츠
        if random.random() < 0.3:
            content = random.choice(MARKDOWN_CONTENTS)
        else:
            content = random.choice(PLAIN_CONTENTS) + "\n\n" + fake.paragraph(nb_sentences=random.randint(2, 5))

        views = random.randint(0, 500)
        # 공지사항(id=6)은 admin만
        category_id = random.randint(1, 5) if author_id != 1 else random.randint(1, 6)
        created_at = _random_past(180)

        posts_data.append((title, content, None, author_id, category_id, views, created_at))

    async with transactional() as cur:
        await cur.executemany(
            """INSERT INTO post (title, content, image_url, author_id, category_id, views, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            posts_data,
        )
    print(f"  ✓ 게시글 {n}개 (마크다운 ~30%)")


# ─────────────────────────────────────────────
# 댓글 (대댓글 포함)
# ─────────────────────────────────────────────


async def seed_comments(cfg: dict):
    """댓글 데이터 생성 (20% 대댓글 포함)."""
    n = cfg["comments"]
    print(f"댓글 {n}개 생성 중...")

    # 1단계: 루트 댓글 (80%)
    root_count = int(n * 0.8)
    root_data = []
    for _ in range(root_count):
        content = random.choice(COMMENT_TEMPLATES) + " " + fake.sentence()
        author_id = random.randint(1, cfg["users"])
        post_id = random.randint(1, cfg["posts"])
        created_at = _random_past(60)
        root_data.append((content, author_id, post_id, None, created_at))

    async with transactional() as cur:
        await cur.executemany(
            """INSERT INTO comment (content, author_id, post_id, parent_id, created_at)
            VALUES (%s, %s, %s, %s, %s)""",
            root_data,
        )

    # 2단계: 대댓글 (20%) — 루트 댓글의 id를 parent_id로 참조
    reply_count = n - root_count
    reply_data = []
    for _ in range(reply_count):
        parent_id = random.randint(1, root_count)
        content = random.choice(COMMENT_TEMPLATES) + " " + fake.sentence()
        author_id = random.randint(1, cfg["users"])
        reply_data.append((content, author_id, parent_id))

    if reply_data:
        async with transactional() as cur:
            # 대댓글의 post_id를 부모 댓글에서 가져와 삽입
            for content, author_id, parent_id in reply_data:
                await cur.execute("SELECT post_id FROM comment WHERE id = %s", (parent_id,))
                row = await cur.fetchone()
                if row:
                    created_at = _random_past(30)
                    await cur.execute(
                        """INSERT INTO comment (content, author_id, post_id, parent_id, created_at)
                        VALUES (%s, %s, %s, %s, %s)""",
                        (content, author_id, row[0], parent_id, created_at),
                    )

    print(f"  ✓ 댓글 {n}개 (루트 {root_count}, 대댓글 {reply_count})")


# ─────────────────────────────────────────────
# 좋아요 / 북마크 / 댓글 좋아요
# ─────────────────────────────────────────────


async def seed_post_likes(cfg: dict):
    """게시글 좋아요 생성."""
    n = cfg["post_likes"]
    pairs = _unique_pairs(n, cfg["users"], cfg["posts"])
    print(f"게시글 좋아요 {len(pairs)}개 생성 중...")

    data = [(u, p, _random_past(60)) for u, p in pairs]
    async with transactional() as cur:
        await cur.executemany(
            "INSERT IGNORE INTO post_like (user_id, post_id, created_at) VALUES (%s, %s, %s)",
            data,
        )
    print(f"  ✓ 게시글 좋아요 {len(pairs)}개")


async def seed_bookmarks(cfg: dict):
    """북마크 생성."""
    n = cfg["bookmarks"]
    pairs = _unique_pairs(n, cfg["users"], cfg["posts"])
    print(f"북마크 {len(pairs)}개 생성 중...")

    data = [(u, p, _random_past(60)) for u, p in pairs]
    async with transactional() as cur:
        await cur.executemany(
            "INSERT IGNORE INTO post_bookmark (user_id, post_id, created_at) VALUES (%s, %s, %s)",
            data,
        )
    print(f"  ✓ 북마크 {len(pairs)}개")


async def seed_comment_likes(cfg: dict):
    """댓글 좋아요 생성."""
    n = cfg["comment_likes"]
    pairs = _unique_pairs(n, cfg["users"], cfg["comments"])
    print(f"댓글 좋아요 {len(pairs)}개 생성 중...")

    data = [(u, c, _random_past(30)) for u, c in pairs]
    async with transactional() as cur:
        await cur.executemany(
            "INSERT IGNORE INTO comment_like (user_id, comment_id, created_at) VALUES (%s, %s, %s)",
            data,
        )
    print(f"  ✓ 댓글 좋아요 {len(pairs)}개")


# ─────────────────────────────────────────────
# 팔로우 / 차단
# ─────────────────────────────────────────────


async def seed_follows(cfg: dict):
    """팔로우 관계 생성."""
    n = cfg["follows"]
    pairs = _unique_pairs(n, cfg["users"], cfg["users"], exclude_same=True)
    print(f"팔로우 {len(pairs)}개 생성 중...")

    data = [(a, b, _random_past(90)) for a, b in pairs]
    async with transactional() as cur:
        await cur.executemany(
            "INSERT IGNORE INTO user_follow (follower_id, following_id, created_at) VALUES (%s, %s, %s)",
            data,
        )
    print(f"  ✓ 팔로우 {len(pairs)}개")


async def seed_blocks(cfg: dict):
    """사용자 차단 생성."""
    n = cfg["blocks"]
    pairs = _unique_pairs(n, cfg["users"], cfg["users"], exclude_same=True)
    print(f"차단 {len(pairs)}개 생성 중...")

    data = [(a, b, _random_past(60)) for a, b in pairs]
    async with transactional() as cur:
        await cur.executemany(
            "INSERT IGNORE INTO user_block (blocker_id, blocked_id, created_at) VALUES (%s, %s, %s)",
            data,
        )
    print(f"  ✓ 차단 {len(pairs)}개")


# ─────────────────────────────────────────────
# 태그
# ─────────────────────────────────────────────


async def seed_tags(cfg: dict):
    """태그 + 게시글-태그 연결 생성."""
    n = min(cfg["tags"], len(TAG_NAMES))
    print(f"태그 {n}개 + 게시글 연결 생성 중...")

    tags = TAG_NAMES[:n]
    async with transactional() as cur:
        await cur.executemany(
            "INSERT IGNORE INTO tag (name) VALUES (%s)",
            [(t,) for t in tags],
        )

        # 각 게시글에 0~3개 태그 연결 (약 60% 게시글에 태그 부여)
        post_tag_data = []
        for post_id in range(1, cfg["posts"] + 1):
            if random.random() < 0.6:
                num_tags = random.randint(1, min(3, n))
                selected_tag_ids = random.sample(range(1, n + 1), num_tags)
                for tag_id in selected_tag_ids:
                    post_tag_data.append((post_id, tag_id))

        if post_tag_data:
            await cur.executemany(
                "INSERT IGNORE INTO post_tag (post_id, tag_id) VALUES (%s, %s)",
                post_tag_data,
            )

    print(f"  ✓ 태그 {n}개, 연결 {len(post_tag_data)}개")


# ─────────────────────────────────────────────
# 위키 (FAQ 스타일)
# ─────────────────────────────────────────────


async def seed_wiki_pages(cfg: dict):
    """FAQ 스타일 위키 페이지 + 태그 연결 생성."""
    n = min(cfg["wiki_pages"], len(WIKI_PAGES_DATA))
    print(f"위키 페이지 {n}개 생성 중...")

    async with transactional() as cur:
        for i in range(n):
            title, slug, content, tag_names = WIKI_PAGES_DATA[i]
            author_id = random.randint(1, cfg["users"])
            views_count = random.randint(10, 500)
            created_at = _random_past(120)

            await cur.execute(
                """INSERT INTO wiki_page (title, slug, content, author_id, views_count, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)""",
                (title, slug, content, author_id, views_count, created_at),
            )
            wiki_page_id = cur.lastrowid

            # 태그 연결 (기존 tag 테이블에서 id 조회)
            for tag_name in tag_names:
                await cur.execute("SELECT id FROM tag WHERE name = %s", (tag_name,))
                row = await cur.fetchone()
                if row:
                    await cur.execute(
                        "INSERT IGNORE INTO wiki_page_tag (wiki_page_id, tag_id) VALUES (%s, %s)",
                        (wiki_page_id, row[0]),
                    )

    print(f"  ✓ 위키 페이지 {n}개 (FAQ, 태그 연결)")


# ─────────────────────────────────────────────
# 투표
# ─────────────────────────────────────────────


async def seed_polls(cfg: dict):
    """투표 (poll + option + vote) 생성."""
    n = min(cfg["polls"], len(POLL_QUESTIONS), cfg["posts"])
    print(f"투표 {n}개 생성 중...")

    poll_post_ids = random.sample(range(1, cfg["posts"] + 1), n)
    poll_post_ids.sort()

    async with transactional() as cur:
        for idx, post_id in enumerate(poll_post_ids):
            question, options = POLL_QUESTIONS[idx % len(POLL_QUESTIONS)]

            # 50% 확률로 만료일 설정 (미래)
            expires_at = (datetime.now() + timedelta(days=random.randint(1, 30))) if random.random() < 0.5 else None

            await cur.execute(
                "INSERT INTO poll (post_id, question, expires_at) VALUES (%s, %s, %s)",
                (post_id, question, expires_at),
            )
            poll_id = cur.lastrowid

            option_ids = []
            for sort_order, opt_text in enumerate(options):
                await cur.execute(
                    "INSERT INTO poll_option (poll_id, option_text, sort_order) VALUES (%s, %s, %s)",
                    (poll_id, opt_text, sort_order),
                )
                option_ids.append(cur.lastrowid)

            # 투표 참여 (랜덤 사용자 5~15명)
            voter_count = min(random.randint(5, 15), cfg["users"])
            voters = random.sample(range(1, cfg["users"] + 1), voter_count)
            for voter_id in voters:
                chosen_option = random.choice(option_ids)
                await cur.execute(
                    "INSERT IGNORE INTO poll_vote (poll_id, option_id, user_id) VALUES (%s, %s, %s)",
                    (poll_id, chosen_option, voter_id),
                )

    print(f"  ✓ 투표 {n}개 (각 5~15명 참여)")


# ─────────────────────────────────────────────
# 패키지 + 리뷰
# ─────────────────────────────────────────────


async def seed_packages():
    """샘플 패키지 데이터 생성 (admin user id=1이 등록)."""
    print(f"패키지 {len(PACKAGES)}개 생성 중...")

    async with transactional() as cur:
        await cur.executemany(
            """INSERT IGNORE INTO package
            (name, display_name, description, homepage_url, category, package_manager, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, 1)""",
            PACKAGES,
        )
    print(f"  ✓ 패키지 {len(PACKAGES)}개 (created_by=admin)")


async def seed_package_reviews(cfg: dict):
    """패키지 리뷰 생성 (평점 1~5 균등 분포)."""
    n = cfg["package_reviews"]
    num_packages = len(PACKAGES)
    print(f"패키지 리뷰 {n}개 생성 중...")

    # (package_id, user_id) 유니크 쌍 생성
    pairs = _unique_pairs(n, num_packages, cfg["users"])

    data = []
    for pkg_id, user_id in pairs:
        rating = random.randint(1, 5)
        title = random.choice(REVIEW_TITLES)
        content = random.choice(REVIEW_CONTENTS)
        created_at = _random_past(90)
        data.append((pkg_id, user_id, rating, title, content, created_at))

    async with transactional() as cur:
        await cur.executemany(
            """INSERT IGNORE INTO package_review
            (package_id, user_id, rating, title, content, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)""",
            data,
        )
    print(f"  ✓ 패키지 리뷰 {len(pairs)}개 (평점 1~5 균등)")


# ─────────────────────────────────────────────
# 알림 설정
# ─────────────────────────────────────────────


async def seed_notification_settings(cfg: dict):
    """일부 사용자의 알림 설정 커스텀 (나머지는 기본 ON)."""
    n = cfg["notification_settings"]
    print(f"알림 설정 {n}개 생성 중...")

    user_ids = random.sample(range(1, cfg["users"] + 1), min(n, cfg["users"]))
    setting_fields = ["comment_enabled", "like_enabled", "mention_enabled", "follow_enabled", "bookmark_enabled"]

    data = []
    for user_id in user_ids:
        # 각 타입별로 20% 확률로 OFF
        settings = [0 if random.random() < 0.2 else 1 for _ in setting_fields]
        data.append((user_id, *settings))

    async with transactional() as cur:
        await cur.executemany(
            """INSERT IGNORE INTO notification_setting
            (user_id, comment_enabled, like_enabled, mention_enabled, follow_enabled, bookmark_enabled)
            VALUES (%s, %s, %s, %s, %s, %s)""",
            data,
        )
    print(f"  ✓ 알림 설정 {len(user_ids)}명 (각 타입 ~20% OFF)")


# ─────────────────────────────────────────────
# 알림
# ─────────────────────────────────────────────


async def seed_notifications(cfg: dict):
    """알림 데이터 생성."""
    n = cfg["notifications"]
    print(f"알림 {n}개 생성 중...")

    notif_types = ["comment", "like", "mention", "follow", "bookmark"]
    data = []
    for _ in range(n):
        user_id = random.randint(1, cfg["users"])
        actor_id = random.randint(1, cfg["users"])
        # 자기 자신에게 알림 안 감
        while actor_id == user_id:
            actor_id = random.randint(1, cfg["users"])

        ntype = random.choice(notif_types)
        # follow는 post_id가 NULL
        if ntype == "follow":
            post_id = None
        else:
            post_id = random.randint(1, cfg["posts"])
        comment_id = random.randint(1, cfg["comments"]) if ntype in ("comment", "mention") else None
        is_read = 1 if random.random() < 0.6 else 0
        created_at = _random_past(30)

        data.append((user_id, ntype, post_id, comment_id, actor_id, is_read, created_at))

    async with transactional() as cur:
        await cur.executemany(
            """INSERT INTO notification (user_id, type, post_id, comment_id, actor_id, is_read, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            data,
        )
    print(f"  ✓ 알림 {n}개 (60% 읽음)")


# ─────────────────────────────────────────────
# 신고
# ─────────────────────────────────────────────


async def seed_reports(cfg: dict):
    """신고 데이터 생성."""
    n = cfg["reports"]
    print(f"신고 {n}개 생성 중...")

    data = []
    seen: set[tuple[int, str, int]] = set()
    for _ in range(n):
        reporter_id = random.randint(1, cfg["users"])
        target_type = random.choice(["post", "comment"])
        target_id = random.randint(1, cfg["posts"] if target_type == "post" else cfg["comments"])
        key = (reporter_id, target_type, target_id)
        if key in seen:
            continue
        seen.add(key)

        reason = random.choice(REPORT_REASONS)
        description = fake.sentence() if reason == "other" else None
        status = random.choice(["pending", "pending", "pending", "resolved", "dismissed"])  # 60% pending
        resolved_by = 1 if status != "pending" else None
        resolved_at = _random_past(7) if status != "pending" else None
        created_at = _random_past(30)

        data.append(
            (reporter_id, target_type, target_id, reason, description, status, resolved_by, resolved_at, created_at)
        )

    async with transactional() as cur:
        await cur.executemany(
            """INSERT IGNORE INTO report
            (reporter_id, target_type, target_id, reason, description, status, resolved_by, resolved_at, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            data,
        )
    print(f"  ✓ 신고 {len(data)}개 (~60% pending)")


# ─────────────────────────────────────────────
# 조회 로그 (읽은 글 표시)
# ─────────────────────────────────────────────


async def seed_view_logs(cfg: dict):
    """게시글 조회 로그 생성 (읽은 글 표시용)."""
    n = cfg["view_logs"]
    pairs = _unique_pairs(n, cfg["users"], cfg["posts"])
    print(f"조회 로그 {len(pairs)}개 생성 중...")

    data = [(u, p, _random_past(14)) for u, p in pairs]
    async with transactional() as cur:
        await cur.executemany(
            "INSERT IGNORE INTO post_view_log (user_id, post_id, created_at) VALUES (%s, %s, %s)",
            data,
        )
    print(f"  ✓ 조회 로그 {len(pairs)}개")


# ─────────────────────────────────────────────
# DM (쪽지)
# ─────────────────────────────────────────────


async def seed_dms(cfg: dict):
    """DM 대화 + 메시지 생성."""
    n_conv = cfg["dm_conversations"]
    n_msg = cfg["dm_messages_per_conv"]
    print(f"DM 대화 {n_conv}개 (대화당 ~{n_msg}개 메시지) 생성 중...")

    conv_pairs = _unique_pairs(n_conv, cfg["users"], cfg["users"], exclude_same=True)

    total_messages = 0
    async with transactional() as cur:
        for a, b in conv_pairs:
            p1, p2 = min(a, b), max(a, b)
            created_at = _random_past(30)

            await cur.execute(
                """INSERT IGNORE INTO dm_conversation (participant1_id, participant2_id, last_message_at, created_at)
                VALUES (%s, %s, %s, %s)""",
                (p1, p2, None, created_at),
            )
            conv_id = cur.lastrowid
            if not conv_id:
                continue

            msg_count = random.randint(max(1, n_msg - 2), n_msg + 3)
            last_msg_at = created_at
            for j in range(msg_count):
                sender = p1 if j % 2 == 0 else p2
                content = fake.sentence()
                msg_at = last_msg_at + timedelta(minutes=random.randint(1, 120))
                is_read = 1 if j < msg_count - 1 else (1 if random.random() < 0.5 else 0)

                await cur.execute(
                    """INSERT INTO dm_message (conversation_id, sender_id, content, is_read, created_at)
                    VALUES (%s, %s, %s, %s, %s)""",
                    (conv_id, sender, content, is_read, msg_at),
                )
                last_msg_at = msg_at
                total_messages += 1

            await cur.execute(
                "UPDATE dm_conversation SET last_message_at = %s WHERE id = %s",
                (last_msg_at, conv_id),
            )

    print(f"  ✓ DM 대화 {n_conv}개, 메시지 {total_messages}개")


# ─────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────


async def main():
    """메인 실행 함수."""
    parser = argparse.ArgumentParser(description="커뮤니티 시드 데이터 생성")
    parser.add_argument(
        "--scale",
        choices=["small", "medium", "large"],
        default="small",
        help="데이터 규모 (기본: small)",
    )
    parser.add_argument(
        "--no-confirm",
        action="store_true",
        help="확인 없이 기존 데이터 삭제",
    )
    args = parser.parse_args()
    cfg = SCALE_PRESETS[args.scale]

    print("=" * 50)
    print(f"시드 데이터 생성 (규모: {args.scale})")
    print("=" * 50)
    print(f"  사용자: {cfg['users']}, 게시글: {cfg['posts']}")
    print(f"  댓글: {cfg['comments']}, 좋아요: {cfg['post_likes']}")
    print(f"  태그: {cfg['tags']}, 투표: {cfg['polls']}, DM: {cfg['dm_conversations']}")
    print(f"  위키: {cfg['wiki_pages']}, 패키지 리뷰: {cfg['package_reviews']}")
    print("=" * 50)

    await init_db()

    try:
        if args.no_confirm:
            await clear_existing_data()
        else:
            confirm = input("기존 데이터를 삭제하고 새로 생성할까요? (yes/no): ")
            if confirm.lower() == "yes":
                await clear_existing_data()
            else:
                print("기존 데이터 유지. 중복 시 무시됩니다.")

        start = datetime.now()

        # 순서 중요: FK 의존성에 따라 부모 먼저
        await seed_users(cfg)
        await seed_packages()
        await seed_posts(cfg)
        await seed_comments(cfg)
        await seed_tags(cfg)
        await seed_wiki_pages(cfg)
        await seed_polls(cfg)
        await seed_post_likes(cfg)
        await seed_bookmarks(cfg)
        await seed_comment_likes(cfg)
        await seed_follows(cfg)
        await seed_blocks(cfg)
        await seed_package_reviews(cfg)
        await seed_notification_settings(cfg)
        await seed_notifications(cfg)
        await seed_reports(cfg)
        await seed_view_logs(cfg)
        await seed_dms(cfg)

        elapsed = datetime.now() - start
        print("=" * 50)
        print(f"✓ 시드 완료! 소요 시간: {elapsed.total_seconds():.1f}초")
        print("=" * 50)
        print("  로그인: user1@example.com / Test1234! (admin)")
        print(f"  일반: user2@example.com ~ user{cfg['users']}@example.com / Test1234!")
        print("=" * 50)

    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
