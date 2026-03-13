## Local AI Coding Agent: Hardware & Software Design

### Design Reference | March 2026 | r68

*Drafted with Claude Sonnet 4.6 (Anthropic) as a collaborative research and drafting assistant.*

## 1\. Objective

The goal is to build a fully local, privacy-preserving AI coding agent — a functional analogue
of Claude Code — using open-weight models running on consumer hardware. The system must support
long-context agentic workflows with reliable tool use, multi-file editing, structured development
methodology, and extensibility through language servers and external tool integrations via MCP.

The selected stack centres on three components: OpenCode as the terminal UI agent frontend,
Superpowers as the agentic skills and workflow framework, and llama.cpp as the inference
backend — served locally on a single NVIDIA RTX 4090 workstation with no cloud dependencies.
The preferred primary model is openai/gpt-oss-20b MXFP4: a mixture-of-experts model delivering
~250 t/s generation and full 131K context on 24GB VRAM, with chain-of-thought reasoning and
native tool calling. Devstral-Small-2-24B Q4\_K\_M is available as a coding-specialist
alternative at 98K context.

## 2\. Hardware Baseline

Target machine: Debian 12, KDE Plasma 5.

| Component | Specification |
| --- | --- |
| Motherboard | Gigabyte Z590 AORUS ELITE |
| PSU | be quiet! Dark Power 13 1000W |
| CPU | Intel Core i9-11900 (11th Gen, 8-core/16-thread, 2.50GHz base) |
| RAM | 64 GiB DDR4-3200MHz (4 × 16 GiB) |
| GPU | NVIDIA GeForce RTX 4090 (24GB GDDR6X) |
| Driver / CUDA | 580.126.09 / CUDA 13.0 |
| Usable VRAM | ~22–23GB (display adapter consumes ~1.3GB) |
| Memory Bandwidth | 1,008 GB/s — primary performance bottleneck for token generation |
| OS | Debian 12, KDE Plasma 5 |

## 3\. Conclusion

The RTX 4090 is a more capable inference platform than its consumer positioning suggests. Two
empirical studies underpin this assessment.

The VRAM sweep (§10) establishes that Q8\_0 KV cache quantisation, used alongside Flash
Attention, delivers ~98K usable tokens for dense models (Devstral, DeepSeek-R1-14B) — nearly
double the F16 baseline. For gpt-oss-20b MXFP4, the MoE architecture's compact per-head
dimensions make this a non-issue: the full 131,072-token native context fits with nearly 8GB
to spare at Q8\_0, at a marginal KV cost of ~0.013 MiB/token.

The benchmark study (§14) establishes that gpt-oss-20b MXFP4 on this hardware delivers
prefill throughput of ~10,000–11,000 t/s and generation of ~250 t/s — the latter a direct
consequence of the MoE architecture activating only 3.6B of 20.91B parameters per token,
moving 4.7× less weight through VRAM per generated token than a comparable dense model.
These are single-run figures; a repeat study (§14.4) is planned to establish means and
confidence intervals. Decode speed is bound by the 1,008 GB/s memory bandwidth ceiling and
is insensitive to batch size configuration.

The preferred primary model is **gpt-oss-20b MXFP4**: full native context on 24GB, ~250 t/s
generation, no OpenCode compatibility issues, and chain-of-thought reasoning built in.
Devstral-Small-2-24B Q4\_K\_M remains available as a coding-specialist alternative at 98K
context and ~55 t/s generation. DeepSeek-R1-Distill-Qwen-14B Q6\_K\_L is confirmed to load
and serve correctly; OpenCode tool call compatibility is pending empirical verification.

Language servers and MCP servers run entirely on CPU and can be added incrementally without
any impact on the inference stack. An upgrade to the RTX PRO 6000 Blackwell would remove
the VRAM ceiling entirely — enabling Q8 quality at full context for all three models, and
opening access to larger models such as gpt-oss-120b — but is not required for productive
use of the current stack.

## 4\. Software Stack Overview

The complete stack has four logical layers. Each layer was selected independently on merit, and the full combination is validated to interoperate correctly.

| Layer | Component | Role |
| --- | --- | --- |
| Inference server | llama.cpp llama-server | Hosts the model; OpenAI-compatible REST API on localhost |
| Language model | Devstral-Small-2-24B Q4\_K\_M | Agentic coding model; tool calling; multi-file edits |
| Agent frontend | OpenCode | Terminal UI; session management; LSP; tool dispatch |
| Workflow framework | Superpowers | Skills library; TDD enforcement; subagent orchestration |
| Language servers | Per-language (rust-analyzer, pyright, etc.) | Semantic code intelligence; go-to-definition; diagnostics |
| MCP servers | SearXNG, trilium-bolt, awslabs/mcp, etc. | External capabilities; web search; notes; AWS |

## 5\. Custom Kernel Build

The NVIDIA driver installer requires the kernel source and build directory. The stock Debian kernel works, but a custom build lets you control the version, strip debug symbols, and set a unique Build ID for reproducibility. The Build ID salt is set via `scripts/config --set-str CONFIG_BUILD_SALT` as shown in §5.2, or interactively under `General setup → Build ID Salt`. Recommended format: `${LOCAL_VERSION}-YYYYMMDD`. This distinguishes builds, links binaries to debug symbols, and supports reproducibility.

### 5.1 Prerequisites

```
sudo apt install linux-source firmware-realtek firmware-linux libncurses-dev
```

The firmware packages required will vary by motherboard. `firmware-realtek` and `firmware-linux` are the right mix for the author's hardware — check your own system's firmware needs before installing.

### 5.2 Build Flow

```
# Update and install sources
sudo apt update && sudo apt upgrade
sudo apt install linux-source

# Linux source package we'll use
PKG_LINUX_SOURCE="linux-source-6.1"

# Fetch the kernel version number from package metadata
KERNEL_VERSION=$(dpkg-query -W -f='${Version}\n' ${PKG_LINUX_SOURCE} | cut -d- -f1)

# Decide on a meaningful suffix for the custom kernel package; this becomes the
# LOCALVERSION argument to 'make deb-pkg' and uniquifies the build directory name
LOCAL_VERSION="ceb"

# Create a build directory and unpack
mkdir ~/kernel/${KERNEL_VERSION}-${LOCAL_VERSION} && cd ~/kernel/${KERNEL_VERSION}-${LOCAL_VERSION}
cp /usr/src/${PKG_LINUX_SOURCE}.tar.xz .
tar xf ${PKG_LINUX_SOURCE}.tar.xz
cd ${PKG_LINUX_SOURCE}

# Confirm the kernel version from sources
make kernelversion

# Seed config from running kernel, accept all new defaults
make olddefconfig

# Set Build ID salt to ${LOCAL_VERSION}-YYYYMMDD
scripts/config --set-str CONFIG_BUILD_SALT "${LOCAL_VERSION}-$(date +%Y%m%d)"

# Disable debug symbols
scripts/config --set-val CONFIG_DEBUG_INFO n

# Build Debian packages using all available cores
make -j$(nproc) deb-pkg LOCALVERSION=-${LOCAL_VERSION} KDEB_PKGVERSION=${KERNEL_VERSION}-1 2>&1 | tee build.log
```

### 5.3 Install

```
cd ~/kernel/${KERNEL_VERSION}-${LOCAL_VERSION}
sudo dpkg -i linux-image-${KERNEL_VERSION}-${LOCAL_VERSION}_*.deb
sudo dpkg -i linux-headers-${KERNEL_VERSION}-${LOCAL_VERSION}_*.deb
sudo dpkg -i linux-libc-dev_*.deb
sudo reboot
```

### 5.4 Package Notes

`make deb-pkg` produces up to 5 packages. You need only `linux-image-*` (kernel + modules), `linux-headers-*` (required for external modules including the NVIDIA driver), and `linux-libc-dev` (userspace headers). Skip `linux-image-*-dbg` (800 MB+) unless doing kernel debugging. The debug package may build anyway despite `CONFIG_DEBUG_INFO=n` — just don't install it.

### 5.5 Keeping Build Dependencies

Mark build tools as manually installed so apt doesn't remove them:

```
sudo apt-mark manual linux-compiler-gcc-12-x86 linux-kbuild-6.1
```

### 5.6 Removing Old Kernels

Keep the two most recent. Old kernels accumulate in `/boot` (limited partition) and `/usr/lib/debug/` (debug symbols, multiple GB).

```
sudo apt purge linux-image-6.1.X-Y linux-headers-6.1.X-Y
sudo apt autoremove --purge
df -h /boot   # verify free space
```

### 5.7 References

*   [Debian FAQ — Kernel](https://www.debian.org/doc/manuals/debian-faq/kernel.en.html)
*   [Debian Kernel Handbook](https://kernel-team.pages.debian.net/kernel-handbook/ch-common-tasks.html#s-common-building)
*   [Debian Administrator's Handbook — Compiling a Kernel](https://www.debian.org/doc/manuals/debian-handbook/sect.kernel-compilation.en.html)

## 6\. NVIDIA Accelerated Linux Graphics Driver Installation


### 6.1 Overview

This chapter covers installing the NVIDIA Accelerated Linux Graphics Driver on Debian 12 Bookworm (x86_64) using the official `.run` installer from NVIDIA. It does not use the Debian package manager for the driver itself, for reasons explained in Section 6.3.

The chapter also explains NVIDIA's driver branch naming convention so you can make an informed choice when selecting a driver version from NVIDIA's download pages.


### 6.2 Understanding NVIDIA Driver Branches

When you visit nvidia.com to download a driver for a consumer GPU, the search results present a list of version numbers with no explanation of which one to choose. This section explains the branch numbering and gives a practical selection rule.


#### 6.2.1 Finding and Selecting a Driver

The canonical download page for NVIDIA Linux drivers is:

```
https://www.nvidia.com/en-us/drivers/
```

Use the Manual Driver Search form to locate the correct driver. Select your product type and series, then your specific GPU, then set Operating System → Linux 64-bit and Download Type → Production Branch. Pick the top result. The product type path differs by GPU family — GeForce cards are found under GeForce, while professional cards such as the RTX PRO 6000 Blackwell are found under NVIDIA RTX PRO / RTX / Quadro.

NVIDIA organises driver releases into branches identified by the leading digits of the version number — `580.xxx.yy` belongs to branch R580, `590.xxx.yy` to R590, and so on. Minor releases within a branch deliver bug fixes and security updates; upgrading within a branch is low-risk. **Production Branch** is the stable choice for a workstation; **New Feature Branch** targets early adopters and is not recommended for a stable environment. The [NVIDIA Unix Driver Archive](https://www.nvidia.com/en-us/drivers/unix/) provides a concise enumeration of current branch names and version numbers — as of March 2026: Production Branch → 580.xxx.yy, New Feature → 590.xx.yy, Beta → 595.xx.yy. The [Driver Lifecycle](https://docs.nvidia.com/datacenter/tesla/drivers/driver-lifecycle.html) page covers branch EOL dates and CUDA toolkit compatibility in more depth.

As of March 2026, the current Production Branch on Linux x86_64/AMD64 is **R580** (CUDA 13.x). The downloaded file will be named `NVIDIA-Linux-x86_64-580.xxx.yy.run`.

To verify that a specific driver version supports your GPU before downloading, follow Archive → Linux x86_64 → the specific driver version → Supported Products List on the [NVIDIA Unix Driver Archive](http://www.nvidia.com/object/unix.html). This is the authoritative GPU compatibility reference cited in the driver's own README.


#### 6.2.2 Inspecting the .run File Before Installing

The `.run` file is a self-extracting archive and can be unpacked without touching the system:

```bash
sh NVIDIA-Linux-x86_64-580.xxx.yy.run --extract-only --target NVIDIA-Linux-x86_64-580.xxx.yy
```

This is worth doing before any installation or upgrade. The extracted directory contains a `README.txt` that is the single most informative document NVIDIA provides for Linux driver users — far more so than anything on the consumer download pages. Key contents include:

- **Supported Products list (Appendix A)** — the complete list of every GPU covered by this driver release, with PCI device IDs. A single R580 `.run` file covers hardware ranging from consumer GeForce (RTX 4090, RTX 5090) through professional Blackwell workstation GPUs ([RTX PRO 6000 Blackwell](https://www.nvidia.com/en-us/products/workstations/professional-desktop-gpus/rtx-pro-6000/)) and data centre parts (H100, H200). This breadth is not documented anywhere on the download pages and can only be confirmed from this list or via the unix.html archive path described above.
- **NVIDIA_Changelog** — the precise delta between minor releases within the branch, useful for assessing whether an update is worth taking.
- **Installer option reference** — the full `--advanced-options` flag set, including `--kernel-source-path` and other flags relevant to custom kernel builds.
- **INTERACTION WITH THE NOUVEAU DRIVER** — NVIDIA's own guidance on nouveau suppression, which informed the approach documented in section 6.4.3.



### 6.3 Why Use the .run Installer on Debian 12

Debian 12's APT repositories include an `nvidia-driver` package, but it ships an older driver version and is compiled without targeting the specific GPU hardware optimally. The `.run` installer from NVIDIA is preferable here because:

- It provides the current R580 Production Branch driver rather than whatever Debian has packaged.
- It allows explicit control over the `--kernel-source-path`, which is required when running a custom kernel (see Chapter 5).
- It integrates with DKMS, allowing the kernel module to rebuild automatically across kernel updates.

The trade-off is that the `.run` installer operates outside of APT's dependency tracking. The `checkinstall` approach documented in the llama.cpp build section can be applied here too if desired, but is not covered in this chapter.


### 6.4 Prerequisites


#### 6.4.1 Kernel Headers and Build Tools

The NVIDIA installer builds a kernel module against the running kernel. The kernel headers and build directory from section 5.2 must be available.


#### 6.4.2 libglvnd

The vendor-neutral GL dispatch library is required:

```bash
sudo apt install libglvnd-core-dev libglvnd-dev libglvnd0
```


#### 6.4.3 Nouveau and GRUB Kernel Parameters

The open-source `nouveau` driver must not be performing a kernel modeset when the NVIDIA driver is installed. Full blacklisting is not necessary — suppressing the modeset is sufficient. Add the following to `GRUB_CMDLINE_LINUX_DEFAULT` in `/etc/default/grub`:

```
GRUB_CMDLINE_LINUX_DEFAULT="quiet nouveau.modeset=0 nvidia-drm.modeset=1"
```

`nouveau.modeset=0` prevents Nouveau from performing a kernel modeset. Without the modeset, Nouveau's kernel module can be unloaded even if it does load, and the NVIDIA installer will not be blocked by it.

`nvidia-drm.modeset=1` enables DRM kernel mode setting for the NVIDIA driver. This is required for Wayland support, PRIME render offload, and correct behaviour of several compute and display features. It should be set from the outset rather than added later.

After editing `/etc/default/grub`, update GRUB and reboot:

```bash
sudo update-grub
sudo reboot
```

After rebooting, verify Nouveau is not holding a modeset:

```bash
lsmod | grep nouveau
```

Output may show the module is loaded but that is not a problem — what matters is that it has not performed a modeset. If the module is listed, it will be displaced cleanly when the NVIDIA module loads during installation.


### 6.5 Uninstalling a Previous Driver

If a previous NVIDIA driver is installed, uninstall it before proceeding. Using the same `.run` installer:

```bash
sudo ./NVIDIA-Linux-x86_64-580.xxx.yy.run --uninstall
```

Or, if the previous installation was via a different `.run` file:

```bash
sudo nvidia-uninstall
```

If the driver was installed via APT, remove it through the package manager instead:

```bash
sudo apt remove --purge nvidia-driver nvidia-kernel-dkms
sudo apt autoremove
```


### 6.6 Installation

Make the installer executable and run it, specifying the kernel source path and the libglvnd EGL config path:

```bash
chmod +x NVIDIA-Linux-x86_64-580.xxx.yy.run

sudo ./NVIDIA-Linux-x86_64-580.xxx.yy.run \
  --kernel-source-path $HOME/kernel/${KERNEL_VERSION}-${LOCAL_VERSION}/${PKG_LINUX_SOURCE} \
  --glvnd-egl-config-path /usr/lib/x86_64-linux-gnu/pkgconfig
```

Adjust `--kernel-source-path` to match the location of your kernel source tree. For a stock Debian kernel the installer will find the headers automatically via `/lib/modules/$(uname -r)/build` and the flag can be omitted.

**Installer prompts to expect:**

During the ncurses-based installer, you will be asked several questions. The non-default responses required for a typical Debian 12 setup are:

- **"Would you like to register the kernel module with DKMS?"** — Answer **Yes**. This allows the kernel module to rebuild automatically when you update the kernel, without needing to re-run the installer.
- **"Would you like to rebuild the initramfs?"** — Answer **No** (select "Do not rebuild initramfs"). Nouveau is suppressed via the `nouveau.modeset=0` kernel parameter rather than an initramfs blacklist, so no initramfs rebuild is needed.
- **"Would you like to run nvidia-xconfig?"** — Answer based on your setup. If you are using X11 and do not have an existing `xorg.conf`, answering Yes will create a working configuration automatically.


### 6.7 Verifying the Installation

After installation, reboot to load the new kernel module:

```bash
sudo reboot
```

Verify the driver is loaded and the GPU is recognised:

```bash
nvidia-smi
```

Expected output (abbreviated):

```
+-----------------------------------------------------------------------------+
| NVIDIA-SMI 580.xxx.yy   Driver Version: 580.xxx.yy   CUDA Version: 13.0   |
|-------------------------------+----------------------+----------------------+
| GPU  Name        Persistence-M| Bus-Id        Disp.A | Volatile Uncorr. ECC |
| Fan  Temp  Perf  Pwr:Usage/Cap|         Memory-Usage | GPU-Util  Compute M. |
|===============================+======================+======================|
|   0  NVIDIA GeForce RTX 4090            Off  | 00000000:XX:00.0 Off |                  N/A |
|  30%   35C    P8    20W / 450W |      4MiB / 24564MiB |      0%      Default |
+-----------------------------------------------------------------------------+
```

Check the kernel module is loaded:

```bash
lsmod | grep nvidia
```

Expected output includes: `nvidia`, `nvidia_modeset`, `nvidia_uvm`, `nvidia_drm`.


### 6.8 Updating the Driver

When a new minor release appears within the R580 branch (e.g. a future `580.xxx.yy`), updating is straightforward:

1. Download the new `.run` file from nvidia.com.
2. The running NVIDIA module must not be in use. If X11 or a display manager is running, stop it first: `sudo systemctl stop gdm` (or equivalent for your display manager).
3. Run the new installer with the same flags as the original installation.

Because DKMS was registered during installation, kernel module rebuilds across kernel updates happen automatically without needing to re-run the installer.

To check the currently installed driver version at any time without re-running the installer:

```bash
cat /proc/driver/nvidia/version
```


### 6.9 References

- NVIDIA Driver Downloads: https://www.nvidia.com/en-us/drivers/
- NVIDIA Linux Drivers (branch-to-version listing): https://www.nvidia.com/en-us/drivers/unix/
- NVIDIA Unix Driver Archive (Supported Products List per version): http://www.nvidia.com/object/unix.html
- NVIDIA Data Center Driver Lifecycle documentation: https://docs.nvidia.com/datacenter/tesla/drivers/driver-lifecycle.html
- Companion guide — Kernel Build: Chapter 5 of this document
- Companion guide — llama.cpp build (CUDA setup reference): Chapter 7 of this document


## 7\. CUDA Toolkit Installation

The NVIDIA driver (`nvidia-smi`) and the CUDA toolkit (`nvcc`) are separate packages. The toolkit must be installed from NVIDIA's official Debian 12 repository before building llama.cpp.

**Do not use** `sudo apt install nvidia-cuda-toolkit` — Debian 12 Bookworm's repos only ship CUDA 11.8, which is too old.

### 7.1 Add NVIDIA's Debian 12 Repository

```
mkdir -p ~/build/cuda-toolkit
cd ~/build/cuda-toolkit
wget https://developer.download.nvidia.com/compute/cuda/repos/debian12/x86_64/cuda-keyring_1.1-1_all.deb
sudo dpkg -i cuda-keyring_1.1-1_all.deb
sudo apt update
```

### 7.2 Install the Toolkit

```
sudo apt install cuda-toolkit-13-0
```

Using `cuda-toolkit-13-0` rather than the `cuda` meta-package is important — the meta-package attempts to install or upgrade drivers, which can conflict with an already-working manually installed driver.

### 7.3 Configure PATH and Library Path

The NVIDIA apt package installs to `/usr/local/cuda-13.0/` (symlinked as `/usr/local/cuda/`) but does not update PATH automatically.

Add the following to `~/.bashrc`:

```
echo 'export PATH=/usr/local/cuda/bin:$PATH' >> ~/.bashrc
echo 'export LD_LIBRARY_PATH=/usr/local/cuda/lib64${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}' >> ~/.bashrc
source ~/.bashrc
```

The `${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}` syntax safely handles the case where `LD_LIBRARY_PATH` is unset, avoiding a leading colon in the path.

### 7.4 Verify

```
nvcc --version
```

Expected output:

```
nvcc: NVIDIA (R) Cuda compiler driver
Copyright (c) 2005-2025 NVIDIA Corporation
Cuda compilation tools, release 13.0, V13.0.88
```

## 8\. Models

This chapter covers all models evaluated for use in this stack. Each model is documented with its
key properties, quantisation options, llama-server configuration, and any known compatibility
issues with OpenCode. Empirical VRAM measurements for all models are in Chapter 10.

### 8.1 Model Selection Criteria

Models are evaluated against the following requirements, in priority order:

**VRAM fit.** The model weights plus KV cache at a useful context length must fit within 24GB.
Useful means at minimum 32K tokens; 96K+ is preferred for long agentic sessions.

**Tool calling.** Native structured tool call support is required. OpenCode dispatches file reads,
shell commands, and code edits as tool calls; a model that cannot reliably follow tool call
format is not usable as a coding agent.

**Licence.** Apache 2.0 or equivalent permissive licence. No research-only or non-commercial
restrictions.

**llama.cpp support.** The model architecture must be supported by the current mainline
llama.cpp build. Architectures requiring custom branches or forks are deferred until support
lands in mainline.

**OpenCode compatibility.** The model's chat template must handle OpenCode's message structure
without errors. OpenCode sends multiple system messages per request; Mistral-family models with
strict role alternation enforcement require a workaround (see §11.5).

### 8.2 GGUF Sources and Reputable Quantizers

Quantised GGUF files are produced and published by third parties, not by the original model authors. The quality of the quantization — and in particular whether the embedded chat template is correct — depends on who did the work.

[bartowski](https://huggingface.co/bartowski) is the recommended source for Devstral and most other mainstream model quantizations. The reasons to treat this source as reputable are concrete:

**Professional background.** bartowski is a Research Engineer at Arcee AI, a company focused on language model development. This is not a hobbyist doing ad-hoc conversions.

**Community standing.** Nearly 9,300 followers on Hugging Face — unusually high for an individual quantizer. The community has validated the quality of the work over time and across many models, and any systematic errors would have been surfaced and reported long ago.

**Active upstream contributor.** bartowski submits PRs directly to llama.cpp — including chat template fixes for specific models. Someone contributing to the very tool you are using has both the expertise and the incentive to get things right.

**Volume and consistency.** Essentially every significant model release is quantized quickly and consistently, giving a long public track record.

**LM Studio affiliation.** The quantizations are also validated through a separate toolchain with its own large user base.

"Reputable" here is not a formal Hugging Face designation — it is earned trust, established through a public record of professional-quality work that others have validated.

### 8.3 Chat Template Handling

The chat template defines how conversation turns, system prompts, and tool calls are formatted before being passed to the model. Getting this wrong produces garbled outputs, exposed special tokens, or silently broken tool calls.

For well-maintained GGUF files from reputable sources, no manual configuration is required. The chat template is embedded directly in the GGUF file by the quantizer and llama.cpp reads and applies it automatically at load time. In the llama-server startup log this appears as:

```
tokenizer.chat_template str = {#- Default system message if no syst...
```

When `--jinja` is passed to llama-server (as required for Devstral tool calls — see Section 9.1), llama.cpp uses this embedded template to format all prompts correctly without any additional configuration.

The cases where manual template intervention is needed are:

**llama-cli conversation mode.** The `--chat-template mistral` flag used in the llama-cli examples in Section 9 is a belt-and-suspenders measure. It is redundant when the template is embedded correctly, but harmless and makes the intent explicit.

**Missing or incorrect embedded template.** Rare with well-maintained quantizations, but can happen with hastily converted models. Symptoms are garbled output or exposed special tokens. Can be overridden with `--chat-template <name>` or `--chat-template-file <path>`.

**Direct API access.** When hitting the `/v1/chat/completions` endpoint with a properly structured message array, llama-server applies the embedded template automatically. No manual template handling is needed in the calling code.


### 8.4 Devstral-Small-2-24B (Primary — agentic coding specialist)

`mistralai/Devstral-Small-2-24B-Instruct-2512` on HuggingFace. Purpose-built for agentic
software engineering, with training specifically targeting codebase exploration, multi-file
editing, tool calling, and bash execution — exactly the operations OpenCode dispatches.

**Key properties:**

*   **SWE-Bench Verified:** 68.0% — only 4.2 points below its 123B sibling. The strongest
    open-weight agentic coding model at this parameter count at time of writing.
*   **Architecture:** Dense transformer, 23.6B parameters, all active per token.
*   **Context window:** 256K tokens native. Practical limit on RTX 4090 is ~98K tokens
    (empirically measured — see §10.3).
*   **Tool calling:** Native structured tool call support via Jinja chat template. Requires
    `--jinja` flag in llama-server.
*   **OpenCode compatibility:** Requires patched chat template workaround (see §11.5).
*   **License:** Apache 2.0.

**Download:**

```bash
huggingface-cli download bartowski/mistralai_Devstral-Small-2-24B-Instruct-2512-GGUF \
  mistralai_Devstral-Small-2-24B-Instruct-2512-Q4_K_M.gguf \
  --local-dir ~/gguf/
```

**Quantisation options on RTX 4090:**

| Quantisation | Weight Size | Context at 24GB VRAM | Quality vs FP16 | Recommendation |
| --- | --- | --- | --- | --- |
| IQ4\_XS | ~13.5GB | ~110K tokens | ~97% (calibrated) | Max context |
| **Q4\_K\_M** | **~14GB** | **~98K tokens** | **~95%** | **Recommended** |
| Q5\_K\_M | ~17GB | ~54K tokens | ~97% | Quality focus |
| Q8\_0 | ~25GB | OOM on 24GB | ~99% | Requires upgrade |

All figures assume `--cache-type-k q8_0 --cache-type-v q8_0` and `--flash-attn on`. Without KV
quantisation, usable context roughly halves.

**llama-server configuration:**

```bash
llama-server \
  --model ~/gguf/mistralai_Devstral-Small-2-24B-Instruct-2512-Q4_K_M.gguf \
  --n-gpu-layers 99 \
  --ctx-size 98304 \
  --cache-type-k q8_0 \
  --cache-type-v q8_0 \
  --flash-attn on \
  --jinja \
  --chat-template-file ~/gguf/devstral_chat_template_patched.jinja \
  --port 8001 \
  --host 127.0.0.1 2>&1 | tee -a "$LOG"
```

See §11.5 for the rationale behind `--chat-template-file` and how to produce the patched
template. Remove this flag once OpenCode PR #15018 ships in a released version.


### 8.5 openai/gpt-oss-20b (Primary — general reasoning, preferred)

`openai/gpt-oss-20b` on HuggingFace. OpenAI's first open-weight model release (August 2025).
A mixture-of-experts reasoning model with native chain-of-thought capabilities, designed for
agentic tasks including tool calling and code generation. Preferred over Devstral for daily use
based on observed performance: approximately 3× faster generation, full 131K context with
comfortable VRAM headroom, and no OpenCode compatibility issues.

**Key properties:**

*   **Architecture:** Mixture-of-experts (MoE) — 32 experts, 4 active per token. 20.91B total
    parameters, 3.6B active per forward pass.
*   **Layers:** 24 transformer layers with hybrid attention: 12 global attention layers and 12
    sliding window attention (SWA) layers (`n_swa = 128`).
*   **Context window:** 131,072 tokens native; fits in full on RTX 4090 with 6GB+ headroom
    (empirically measured — see §10).
*   **Reasoning:** Native chain-of-thought via the harmony response format. Reasoning effort
    adjustable via `Reasoning: low / medium / high` in the system prompt.
*   **Tool calling:** Supported natively via `<|call|>` and `<|flush|>` tokens.
*   **Quantisation:** MXFP4 is the native training precision of the MoE feed-forward layers —
    not a post-hoc compression. The MXFP4 GGUF is the full-quality model.
*   **OpenCode compatibility:** Works without modification. No chat template patching required.
*   **License:** Apache 2.0.
*   **Tokenizer:** GPT-4o tokenizer (BPE, 201,088 vocabulary).

**The MXFP4 format.** MXFP4 (Microscaling FP4) uses 4-bit mantissa values with a shared
block-level scaling factor, giving higher precision than naive INT4 while remaining more compact
than FP8. For gpt-oss-20b the MoE feed-forward layers were trained at MXFP4 precision, making
this the native representation rather than a lossy conversion. The GGUF tensor breakdown: 289
f32 tensors (norms, embeddings, attention projections), 98 q8\_0 tensors (attention weights),
72 mxfp4 tensors (MoE expert weights). Native MXFP4 support is in llama.cpp mainline as of
build 8244.

**Download:**

```bash
huggingface-cli download bartowski/openai_gpt-oss-20b-GGUF \
  openai_gpt-oss-20b-MXFP4.gguf \
  --local-dir ~/gguf/
```

**llama-server configuration:**

```bash
llama-server \
  --model ~/gguf/openai_gpt-oss-20b-MXFP4.gguf \
  --n-gpu-layers 99 \
  --ctx-size 0 \
  --cache-type-k q8_0 \
  --cache-type-v q8_0 \
  --flash-attn on \
  --jinja \
  --reasoning-format none \
  --batch-size 4096 \
  --ubatch-size 1024 \
  --port 8001 \
  --host 127.0.0.1 2>&1 | tee -a "$LOG"
```

`--ctx-size 0` resolves to the full 131,072 trained context. `--cache-type-k/v q8_0` is
confirmed effective via `llama-cli` context sweep (see §10.5): context allocation at 131,072
tokens drops from 3,126 MiB (F16) to 1,660 MiB (Q8\_0). These flags should be included.

`--reasoning-format none` preserves the `analysis` and `commentary` channel outputs from the harmony response format inline in `message.content`, making them visible in OpenCode and available when the model exports a chat session (see §11.7). Without this flag, llama-server's default `auto` mode strips non-`final` channel content before returning responses to the client. There is no token or context window cost — the flag only controls how response content is surfaced.

**Observed performance (RTX 4090, build 8244):**

| Request | Prompt tokens | Prefill t/s | Generation tokens | Generation t/s |
|---|---|---|---|---|
| Title generation | 594 | 589 | 116 | 78 |
| Main turn 1 | 9,920 | 9,670 | 61 | 126 |
| Main turn 2 (KV cache hit) | 3,954 new | 7,807 | 549 | **175** |

For systematic `llama-bench` results and a cross-hardware comparison, see §14.1–§14.2.

**VRAM allocation at full context (131,072 tokens, Q8\_0 KV cache):**

| Component | Size |
|---|---|
| Model weights | 10,949 MiB |
| KV cache Q8\_0 (all layers) | 1,660 MiB |
| Compute buffer | 1,672 MiB |
| **Total** | **~14,281 MiB** |
| **Free headroom** | **~7,792 MiB** |

With F16 KV cache the context allocation is 3,126 MiB (total ~15,744 MiB, ~6,339 MiB free).
See §10.5 for the full sweep data.

**Chat template — harmony format.** The harmony format uses `<|start|>`, `<|message|>`,
`<|end|>`, and `<|channel|>` tokens. Every assistant message specifies a channel (`analysis`,
`commentary`, or `final`). A `developer` role is supported for instruction framing but is
optional — OpenCode does not send it and the model operates correctly without it.


### 8.6 DeepSeek-R1-Distill-Qwen-14B (Secondary — server confirmed, OpenCode integration pending)

`deepseek-ai/DeepSeek-R1-Distill-Qwen-14B` on HuggingFace. A reasoning model produced by
distilling DeepSeek-R1's chain-of-thought capabilities into a Qwen-based 14B parameter
architecture. Like gpt-oss-20b it produces explicit reasoning traces before answering, but at a
smaller parameter count and with a different training lineage.

llama-server starts cleanly with this model. OpenCode tool call behaviour has not yet been
verified empirically.

**Key properties:**

*   **Architecture:** Dense transformer (Qwen2 base), 14.77B parameters, all active per token.
*   **Context window:** 131,072 tokens native; practical limit 98,304 tokens on RTX 4090
    at Q8\_0 KV cache (see §10.4).
*   **Reasoning:** Chain-of-thought via `<think>` / `</think>` tags. llama.cpp detects the
    reasoning template automatically (`thinking = 1` at startup); no extra flags required.
*   **Chat template:** Qwen DeepSeek variant (`<｜User｜>` / `<｜Assistant｜>` /
    `<｜end▁of▁sentence｜>`). No role alternation strictness — the multi-system-message
    issue seen with Devstral (§11.5) does not apply.
*   **Tool calling:** Supported in principle via the Qwen chat template; not yet verified with
    OpenCode's tool call format.
*   **License:** MIT.

**Download:**

```bash
huggingface-cli download bartowski/DeepSeek-R1-Distill-Qwen-14B-GGUF \
  DeepSeek-R1-Distill-Qwen-14B-Q6_K_L.gguf \
  --local-dir ~/gguf/
```

Q6\_K\_L is recommended: at 11,128 MiB it leaves the same practical context ceiling as Devstral
(98,304 tokens at Q8\_0 KV cache) despite higher per-token KV cost, because the lighter weights
compensate. See §10.4 for the full sweep data.

**llama-server configuration:**

```bash
LOG=~/logs/llama-server-deepseek-r1-14b-$(date '+%Y%m%d_%H%M%S').log
echo "=== Server started: $(date '+%Y-%m-%d %H:%M:%S %Z') ===" > "$LOG"
llama-server \
  --model ~/gguf/DeepSeek-R1-Distill-Qwen-14B-Q6_K_L.gguf \
  --n-gpu-layers 99 \
  --ctx-size 98304 \
  --cache-type-k q8_0 \
  --cache-type-v q8_0 \
  --flash-attn on \
  --jinja \
  --reasoning-format none \
  --port 8001 \
  --host 127.0.0.1 2>&1 | tee -a "$LOG"
```

**`--reasoning-format` flag.** llama-server strips `<think>` reasoning blocks from responses before returning them to the client by default (`auto` mode). This means OpenCode never sees the reasoning traces, and the model cannot include them in a chat export. `--reasoning-format none` leaves the `<think>` tags unparsed inside `message.content`, making them visible in OpenCode's display and available for export. The valid options are `none` (inline in content), `deepseek` (separate `reasoning_content` field), and `deepseek-legacy` (both). `none` is the recommended option for this stack. There is no token or context window cost — reasoning tokens are generated either way; the flag only controls how they are surfaced in the response.

**Startup notes (from empirical log):**

*   llama.cpp projects 21,248 MiB device usage against 22,031 MiB free — only ~783 MiB
    headroom, below llama.cpp's 1,024 MiB target. It logs a warning and aborts the fit attempt
    (since `--n-gpu-layers 99` is user-set), but loads successfully. All 49 layers offload to GPU.
*   KV cache: 9,792 MiB at Q8\_0 with ctx-size 98304 — consistent with §10.4 sweep data.
*   `n_ubatch` is auto-set to 512 (vs 1024 used for Devstral and gpt-oss-20b).
*   Tokenizer warnings about `</s>` and `special_eos_id` are cosmetic quirks of this GGUF;
    llama.cpp overrides them automatically.

**Observed performance (RTX 4090, build 8244, single run — see §14.5):**

*   **Prefill:** ~5,245 t/s at pp2048, declining to ~3,049 t/s at pp32768. Steeper decline
    than gpt-oss-20b due to dense full attention scaling quadratically with sequence length.
*   **Generation:** ~70 t/s at tg128. Faster than Devstral (~55 t/s) despite heavier
    quantisation, because 14.77B parameters move less weight per token than Devstral's 23.6B.

**Open questions:**

*   Does OpenCode's tool call format round-trip correctly through the Qwen chat template?
*   How does coding task quality compare to gpt-oss-20b and Devstral at similar context lengths?


## 9\. Inference Backend: llama.cpp

llama.cpp ([github.com/ggml-org/llama.cpp](https://github.com/ggml-org/llama.cpp)) is a high-performance inference engine for large language models, providing an OpenAI-compatible REST API and broad quantisation support with full CUDA acceleration.

### 9.1 llama.cpp vs Ollama

The most common alternative to llama.cpp directly is Ollama, which uses llama.cpp internally but wraps it in a model management daemon with automatic downloads, a simpler API, and broader tool ecosystem support. OpenCode documents Ollama as a supported provider. For most local inference use cases Ollama is the more ergonomic choice.

For this specific stack, however, three llama.cpp flags are required that Ollama does not expose:

**`--jinja`** — Devstral's tool call format is defined in its Jinja chat template. llama-server's `--jinja` flag activates this template rendering pipeline. Ollama uses its own template engine and does not pass this flag, which means Devstral's tool calls either fail silently or produce malformed output. Since tool dispatch is the core mechanism by which OpenCode executes every agent action — file reads, edits, bash commands, code search — this is not a recoverable limitation.

**`--cache-type-k q8_0`** — KV cache quantisation is what makes long context usable on 24GB. Without it, the KV cache grows at ~0.166MB/token at FP16, limiting usable context to ~54K tokens at Q4\_K\_M. With `-ctk q8_0 -ctv q8_0`, the cost halves to ~0.083MB/token, enabling ~98K tokens at Q4\_K\_M. Ollama does not expose KV cache quantisation options.

**`--ctx-size`** — Ollama defaults all models to a 4,096-token context window regardless of what the model supports. This can be partially worked around by writing a custom `Modelfile` with `PARAMETER num_ctx 32768`, but this does not interact with KV cache quantisation and the workaround is separate from the `--jinja` issue.

The net effect of using Ollama with Devstral on this hardware would be: no reliable tool calls, and approximately one-third of the available context. If a future Ollama release exposes these flags, the choice can be revisited — the ergonomic advantages are real. Until then, llama.cpp directly is the correct inference backend for this stack.

### 9.2 Building llama.cpp

Build from source to ensure the binary is compiled for your exact CUDA version. Prebuilt releases often lag and may not target CUDA 13.0.

**Install build dependencies:**

```
sudo apt install -y build-essential cmake curl git libcurl4-openssl-dev ccache
```

`ccache` is optional but recommended — it caches compilation results and makes subsequent rebuilds significantly faster.

**Clone and build:**

```
git clone https://github.com/ggml-org/llama.cpp
cd llama.cpp

cmake -B build \
  -DGGML_CUDA=ON \
  -DCMAKE_CUDA_ARCHITECTURES=89 \
  -DCMAKE_BUILD_TYPE=Release \
  -DGGML_CUDA_FA_ALL_QUANTS=ON \
  -DBUILD_SHARED_LIBS=OFF \
  -DLLAMA_CURL=ON

cmake --build build --config Release -j$(nproc)
```

`-j$(nproc)` uses all available CPU cores. The build takes 5–10 minutes.

**Key cmake flags:**

`-DGGML_CUDA=ON` — enables the CUDA backend. The flag is prefixed `GGML_` because CUDA support is implemented at the ggml tensor library layer, not the llama.cpp layer.

`-DCMAKE_CUDA_ARCHITECTURES=89` — targets compute capability 8.9, which is the Ada Lovelace architecture used by the RTX 4090. Targeting specifically avoids compiling for every GPU generation and produces a more optimised binary.

`-DCMAKE_BUILD_TYPE=Release` — enables full compiler optimisations.

`-DGGML_CUDA_FA_ALL_QUANTS=ON` — enables Flash Attention support for all quantisation types, including Q4\_K\_M and Q8\_0 KV cache quantisation. Without this flag, `--flash-attn on` may fall back silently to non-Flash-Attention paths for quantised types, reducing the effectiveness of the context window optimisations in Section 9.

### 9.3 Installing llama.cpp with checkinstall

Rather than running `cmake --install` directly (which leaves apt with no knowledge of the installed files), use `checkinstall` to wrap the installation into a `.deb` package that apt can track and remove cleanly.

**Install checkinstall:**

```
sudo apt install checkinstall
sudo mkdir -p ~/packages
```

**Determine the version number:**

llama.cpp uses the git commit count as its build number:

```
LLAMA_VERSION=$(git -C ~/build/llama.cpp rev-list --count HEAD)
echo $LLAMA_VERSION
```

**Run checkinstall:**

```
cd ~/build/llama.cpp/build

LLAMA_VERSION=$(git -C ~/build/llama.cpp rev-list --count HEAD)

sudo checkinstall --pkgname=llama-cpp \
  --pkgversion=${LLAMA_VERSION} \
  --pkgrelease=1 \
  --arch=amd64 \
  --pkglicense=MIT \
  --pkggroup=misc \
  --pakdir=~/packages \
  --fstrans=no \
  cmake --install ~/build/llama.cpp/build
```

**Key checkinstall flags:**

`--fstrans=no` — disables checkinstall's filesystem translation layer, which otherwise interferes with cmake's install step and causes a spurious "No such file or directory" error even when the destination exists.

`--pakdir=~/packages` — saves the generated `.deb` to a known location for future reinstallation.

`cmake --install ~/build/llama.cpp/build` — uses an absolute path rather than `.` because checkinstall changes the working directory internally, which causes cmake to lose track of the build tree if a relative path is used.

**When prompted**, set the summary to:

```
LLM inference engine with CUDA support, built for RTX 4090 (sm_89), CUDA 13.0
```

Set `Requires: cuda-libraries-13-0` in the package values screen. When asked about files inside the home directory (`install_manifest.txt`), answer `y` to list and `y` to exclude.

**Update the shared library cache:**

```
sudo ldconfig
```

**Verify the installation:**

```
llama-cli --version
```

Expected output:

```
ggml_cuda_init: found 1 CUDA devices:
  Device 0: NVIDIA GeForce RTX 4090, compute capability 8.9, VMM: yes
version: 8244 (35bee031e)
built with GNU 12.2.0 for Linux x86_64
```

To verify apt is tracking the package: `dpkg -l | grep llama`. To remove: `sudo apt remove llama-cpp`.

### 9.4 Downloading the Model

The recommended source for Devstral GGUFs is the `bartowski` repository on HuggingFace, which produces high-quality quantisations for Mistral models.

**Create the virtual environment (once):**

```
python3 -m venv ~/venv/huggingface
~/venv/huggingface/bin/pip install huggingface-hub
```

**Download the model:**

```
~/venv/huggingface/bin/huggingface-cli download \
  bartowski/mistralai_Devstral-Small-2-24B-Instruct-2512-GGUF \
  mistralai_Devstral-Small-2-24B-Instruct-2512-Q4_K_M.gguf \
  --local-dir ~/gguf
```

### 9.5 Starting the Server

The default model is gpt-oss-20b MXFP4. Start the server with:

```bash
LOG=~/logs/llama-server-gpt-oss-20b-$(date '+%Y%m%d_%H%M%S').log
echo "=== Server started: $(date '+%Y-%m-%d %H:%M:%S %Z') ===" > "$LOG"
llama-server \
  --model ~/gguf/openai_gpt-oss-20b-MXFP4.gguf \
  --n-gpu-layers 99 \
  --ctx-size 0 \
  --cache-type-k q8_0 \
  --cache-type-v q8_0 \
  --flash-attn on \
  --jinja \
  --reasoning-format none \
  --batch-size 4096 \
  --ubatch-size 1024 \
  --port 8001 \
  --host 127.0.0.1 2>&1 | tee -a "$LOG"
```

`--n-gpu-layers 99` is the conventional instruction to offload all layers to GPU; llama.cpp caps it at the model's actual layer count. `--ctx-size 0` resolves to the full 131,072 trained context. `--reasoning-format none` preserves the harmony format's channel outputs inline in `message.content` so they are visible in OpenCode and included in chat exports (see §11.7). The server exposes an OpenAI-compatible REST API at `http://127.0.0.1:8001/v1` once loaded.

To start with Devstral instead, substitute the model path and adjust flags as specified in §8.4. To start with DeepSeek-R1-14B, see §8.6.

## 10\. Context Window and KV Cache Quantisation

VRAM must be split between model weights and the KV cache — the attention keys and values for all previous tokens, which must be retained to avoid recomputing them on every generation step. The KV cache cost per token varies by model architecture: Devstral Q4\_K\_M costs 0.083 MiB/token at Q8\_0, DeepSeek-R1-Distill-Qwen-14B Q6\_K\_L costs 0.100 MiB/token at Q8\_0, and gpt-oss-20b MXFP4 costs 0.023 MiB/token at F16 — a consequence of its MoE architecture's compact per-head dimensions. Empirical sweep data for each model is in §10.3–§10.5.

KV cache quantisation (`--cache-type-k q8_0 --cache-type-v q8_0`) reduces the per-token cost by a consistent ~1.88× across all three models — empirically confirmed by sweep data in §10.3–§10.5. The flags are effective for gpt-oss-20b despite its hybrid SWA/global architecture; an earlier startup log suggesting otherwise was misleading.

| Quantisation | KV Cache | Usable Context | Notes |
| --- | --- | --- | --- |
| Q5\_K\_M | FP16 | ~35K tokens | Reduced headroom; not recommended |
| Q5\_K\_M | q8\_0 | ~54K tokens | Workable; context-constrained for large refactors |
| Q4\_K\_M | FP16 | ~54K tokens | Not recommended; no headroom advantage over Q5 |
| **Q4\_K\_M** | **q8\_0** | **~98K tokens** | **Recommended configuration** |
| IQ4\_XS | q8\_0 | ~110K tokens | Maximum context on 24GB; marginal quality tradeoff |

### 10.1 Flash Attention and KV Cache Quantisation

Flash Attention and KV cache quantisation are not independent — Flash Attention is a prerequisite for KV cache quantisation in llama.cpp.

Flash Attention restructures how the attention computation accesses memory, processing the KV cache in tiles rather than materialising the full attention matrix at once. This tiled access pattern is what makes it possible to work with quantised (non-native) KV cache formats efficiently — dequantisation can happen on the fly within each tile without a separate pass.

Without `--flash-attn on`, llama.cpp requires the KV cache to be in a format the standard attention kernel can use directly, which means F16 or F32. Specifying `--cache-type-k q8_0` without Flash Attention may silently fall back to F16, or may error — the behaviour has varied across llama.cpp versions.

The practical implication is that `--flash-attn on`, `-ctk q8_0`, and `-ctv q8_0` must always be specified together. They are a single logical unit, not three independent options.

### 10.2 What 98K Tokens Enables

At 98K tokens, the practical calculus for several workload types changes significantly. In practice:

*   **Single and small multi-file work:** 5–15K tokens typical. Fits comfortably with full session history.
*   **Iterative development:** OpenCode and Superpowers work incrementally; files are added and removed from context explicitly, not held simultaneously.
*   **Code review, explanation, test generation:** Typically 3–10K tokens. Well within budget.
*   **Debugging with stack traces:** Relevant source plus trace typically 3–8K tokens.
*   **Large cross-cutting refactors:** Previously a constraint; at 98K, even large multi-file refactors generally fit without decomposition, though decomposing into sequential steps remains good practice.

The Superpowers workflow itself consumes approximately 3–6K tokens per session for skill documents and conversation history, leaving approximately 92–95K tokens for active code and task state.

The hard ceiling on the current hardware is approximately 104K tokens (empirically measured). Beyond ~128K context requires an RTX 5090 or RTX PRO 6000 Blackwell.

### 10.3 mistralai\_Devstral-Small-2-24B-Instruct-2512-Q4\_K\_M VRAM Measurements

Context figures are derived from empirical measurement using `mistralai_Devstral-Small-2-24B-Instruct-2512-Q4_K_M.gguf` on the RTX 4090. The sweep was automated using `llama-cli_ctx-size_sweep.py`, running `--ctx-size` in 8192-token steps and terminating on the first OOM. Each data point was read from the `llama_memory_breakdown_print` summary table that `llama-cli` prints to stdout at the end of each run — the authoritative per-component VRAM breakdown produced by llama.cpp before exit. Total VRAM: 24,077 MiB. Unaccounted (CUDA runtime + display output): ~1,750 MiB.

The command template used for both runs:

```
llama-cli -m ~/gguf/mistralai_Devstral-Small-2-24B-Instruct-2512-Q4_K_M.gguf \
    --gpu-layers 99 \
    --ctx-size <ctx-size> \
    --flash-attn on \
    [-ctk q8_0 -ctv q8_0] \
    -st \
    -p "Write a Python function to reverse a linked list."
```

**F16 KV cache (default, no KV flags):**

| ctx-size | model (MiB) | context (MiB) | compute (MiB) | free (MiB) | MiB/token |
| --- | --- | --- | --- | --- | --- |
| 8192 | 13302 | 1280 | 266 | 7422 | 0.156 |
| 16384 | 13302 | 2560 | 266 | 6142 | 0.156 |
| 24576 | 13302 | 3840 | 300 | 4821 | 0.156 |
| 32768 | 13302 | 5120 | 266 | 3577 | 0.156 |
| 40960 | 13302 | 6400 | 284 | 2277 | 0.156 |
| 49152 | 13302 | 7680 | 308 | 973 | 0.156 |
| 57344 | OOM | OOM | OOM | OOM | — |

Context scales linearly at **0.156 MiB/token**. OOM occurs at 57,344 tokens — only 973 MiB remained free at the preceding step, insufficient for the next 1,280 MiB context increment.

**Q8\_0 KV cache (`--cache-type-k q8_0 --cache-type-v q8_0`):**

| ctx-size | model (MiB) | context (MiB) | compute (MiB) | free (MiB) | MiB/token |
| --- | --- | --- | --- | --- | --- |
| 8192 | 13302 | 680 | 266 | 8060 | 0.083 |
| 16384 | 13302 | 1360 | 266 | 7380 | 0.083 |
| 24576 | 13302 | 2040 | 300 | 6664 | 0.083 |
| 32768 | 13302 | 2720 | 266 | 6020 | 0.083 |
| 40960 | 13302 | 3400 | 284 | 5320 | 0.083 |
| 49152 | 13302 | 4080 | 308 | 4616 | 0.083 |
| 57344 | 13302 | 4760 | 332 | 3912 | 0.083 |
| 65536 | 13302 | 5440 | 292 | 3253 | 0.083 |
| 73728 | 13302 | 6120 | 316 | 2560 | 0.083 |
| 81920 | 13302 | 6800 | 340 | 1875 | 0.083 |
| 90112 | 13302 | 7480 | 364 | 1171 | 0.083 |
| 98304 | 13302 | 8160 | 324 | 531 | 0.083 |
| 106496 | OOM | OOM | OOM | OOM | — |

Context scales linearly at **0.083 MiB/token**. The safe maximum is **98,304 tokens** (531 MiB free). OOM occurs at 106,496 tokens.

**F16 vs Q8\_0 comparison:**

| ctx-size | context F16 (MiB) | context Q8\_0 (MiB) | ratio |
| --- | --- | --- | --- |
| 8192 | 1280 | 680 | 1.88× |
| 16384 | 2560 | 1360 | 1.88× |
| 24576 | 3840 | 2040 | 1.88× |
| 32768 | 5120 | 2720 | 1.88× |
| 40960 | 6400 | 3400 | 1.88× |
| 49152 | 7680 | 4080 | 1.88× |
| 57344 | OOM | 4760 | — |

The F16/Q8\_0 ratio is a consistent **1.88×** across all measured context sizes — slightly less than the theoretical 2.0×. The delta is attributable to per-block metadata overhead in the Q8\_0 format: each quantised block carries a scale factor with no equivalent in F16, reducing the effective compression ratio from 2.0× to ~1.88×.

The compute allocation varies across runs (266–364 MiB) without a clean relationship to context size, consistent across both KV cache configurations. This is runtime allocation jitter, not a systematic effect.

Without Q8\_0 KV cache quantisation, the practical context ceiling on 24GB VRAM is ~49K tokens (last successful F16 step). With Q8\_0, it is **98K tokens** — 1.72× more usable context. KV cache quantisation is not optional at this context size; it is what makes long context possible.

### 10.4 DeepSeek-R1-Distill-Qwen-14B-Q6\_K\_L VRAM Measurements

Context sweep for `DeepSeek-R1-Distill-Qwen-14B-Q6_K_L.gguf` on the RTX 4090, using the same methodology as Section 10.3. Total VRAM: 24,077 MiB. Unaccounted (CUDA runtime + display output): ~1,750 MiB.

The Q6\_K\_L quantisation weighs in at 11,128 MiB — approximately 2,174 MiB lighter than Devstral Q4\_K\_M (13,302 MiB), which opens up meaningful additional headroom for the KV cache.

**F16 KV cache (default):**

| ctx-size | model (MiB) | context (MiB) | compute (MiB) | free (MiB) |
| --- | --- | --- | --- | --- |
| 8192 | 11128 | 1536 | 307 | 9285 |
| 16384 | 11128 | 3072 | 317 | 7739 |
| 24576 | 11128 | 4608 | 375 | 6145 |
| 32768 | 11128 | 6144 | 307 | 4645 |
| 40960 | 11128 | 7680 | 307 | 3087 |
| 49152 | 11128 | 9216 | 398 | 1446 |
| 57344 | OOM | OOM | OOM | OOM |

Context scales linearly at **0.188 MiB/token** — notably higher than Devstral's 0.156 MiB/token at F16. This reflects the larger KV head dimensions of the Qwen architecture. OOM occurs at 57,344 tokens, with only 1,446 MiB remaining at the preceding step.

**Q8\_0 KV cache (`--cache-type-k q8_0 --cache-type-v q8_0`):**

| ctx-size | model (MiB) | context (MiB) | compute (MiB) | free (MiB) |
| --- | --- | --- | --- | --- |
| 8192 | 11128 | 816 | 307 | 9914 |
| 16384 | 11128 | 1632 | 317 | 9088 |
| 24576 | 11128 | 2448 | 375 | 8214 |
| 32768 | 11128 | 3264 | 307 | 7468 |
| 40960 | 11128 | 4080 | 307 | 6652 |
| 49152 | 11128 | 4896 | 398 | 5744 |
| 57344 | 11128 | 5712 | 398 | 4928 |
| 65536 | 11128 | 6528 | 398 | 4112 |
| 73728 | 11128 | 7344 | 398 | 3296 |
| 81920 | 11128 | 8160 | 307 | 2570 |
| 90112 | 11128 | 8976 | 307 | 1754 |
| 98304 | 11128 | 9792 | 328 | 916 |
| 106496 | 11128 | 10608 | 352 | 76 |

Context scales linearly at **0.100 MiB/token** with Q8\_0 — again higher than Devstral's 0.083 MiB/token, consistent with the larger Qwen KV dimensions. The last measured point (106,496 tokens) leaves only 76 MiB free — far below a safe operating margin. The safe maximum is therefore **98,304 tokens** (916 MiB free), matching Devstral's practical ceiling despite the larger per-token KV cost, because the smaller model weights free up the equivalent headroom.

**Comparison with Devstral Q4\_K\_M:**

| Metric | Devstral Q4\_K\_M | DeepSeek Q6\_K\_L | Notes |
| --- | --- | --- | --- |
| Model weight (MiB) | 13,302 | 11,128 | DeepSeek 2,174 MiB lighter |
| KV cost F16 (MiB/token) | 0.156 | 0.188 | Qwen architecture KV overhead |
| KV cost Q8\_0 (MiB/token) | 0.083 | 0.100 | Consistent ~1.88× compression ratio |
| F16 OOM boundary | 57,344 | 57,344 | Coincidentally identical |
| Safe max context (Q8\_0) | 98,304 | 98,304 | Lighter weights offset higher KV cost |
| Free VRAM at safe max (MiB) | 531 | 916 | DeepSeek has more headroom at ceiling |

The two models arrive at the same practical context ceiling by different paths: Devstral carries more weight but has lower KV overhead per token; DeepSeek carries less weight but higher KV overhead. At 98,304 tokens, DeepSeek Q6\_K\_L actually leaves 385 MiB more headroom than Devstral Q4\_K\_M, suggesting it could potentially sustain slightly higher context in practice — though 106,496 tokens (76 MiB free) is not a safe operating point for either model.


### 10.5 openai\_gpt-oss-20b-MXFP4 VRAM Measurements

Context sweep for `openai_gpt-oss-20b-MXFP4.gguf` on the RTX 4090, using the same methodology
as §10.3. Total VRAM: 24,077 MiB. The sweep ran from 8,192 to 131,072 tokens in 8,192-token
steps; no OOM was encountered in either pass. The command template used:

```
llama-cli -m ~/gguf/openai_gpt-oss-20b-MXFP4.gguf \
    --gpu-layers 99 \
    --ctx-size <ctx-size> \
    --flash-attn on \
    --jinja \
    -ub 2048 -b 2048 \
    [-ctk q8_0 -ctv q8_0] \
    -st \
    -p "Write a Python function to reverse a linked list."
```

**F16 KV cache (default, no KV flags):**

| ctx-size | model (MiB) | context (MiB) | compute (MiB) | free (MiB) |
| --- | --- | --- | --- | --- |
| 8192 | 10949 | 246 | 1593 | 9294 |
| 16384 | 10949 | 438 | 1593 | 9102 |
| 24576 | 10949 | 630 | 1593 | 8910 |
| 32768 | 10949 | 822 | 1593 | 8718 |
| 40960 | 10949 | 1014 | 1593 | 8526 |
| 49152 | 10949 | 1206 | 1593 | 8334 |
| 57344 | 10949 | 1398 | 1593 | 8142 |
| 65536 | 10949 | 1590 | 1593 | 7957 |
| 73728 | 10949 | 1782 | 1593 | 7765 |
| 81920 | 10949 | 1974 | 1593 | 7573 |
| 90112 | 10949 | 2166 | 1593 | 7381 |
| 98304 | 10949 | 2358 | 1593 | 7189 |
| 106496 | 10949 | 2550 | 1593 | 6995 |
| 114688 | 10949 | 2742 | 1593 | 6803 |
| 122880 | 10949 | 2934 | 1593 | 6611 |
| 131072 | 10949 | 3126 | 1672 | 6339 |

No OOM encountered. The full 131,072-token native context fits with **6,339 MiB free**.

**Q8\_0 KV cache (`--cache-type-k q8_0 --cache-type-v q8_0`):**

| ctx-size | model (MiB) | context (MiB) | compute (MiB) | free (MiB) |
| --- | --- | --- | --- | --- |
| 8192 | 10949 | 130 | 1593 | 9386 |
| 16384 | 10949 | 232 | 1593 | 9284 |
| 24576 | 10949 | 334 | 1593 | 9182 |
| 32768 | 10949 | 436 | 1593 | 9080 |
| 40960 | 10949 | 538 | 1593 | 8978 |
| 49152 | 10949 | 640 | 1593 | 8876 |
| 57344 | 10949 | 742 | 1593 | 8774 |
| 65536 | 10949 | 844 | 1593 | 8672 |
| 73728 | 10949 | 946 | 1593 | 8570 |
| 81920 | 10949 | 1048 | 1593 | 8468 |
| 90112 | 10949 | 1150 | 1593 | 8366 |
| 98304 | 10949 | 1252 | 1593 | 8264 |
| 106496 | 10949 | 1354 | 1593 | 8160 |
| 114688 | 10949 | 1456 | 1593 | 8076 |
| 122880 | 10949 | 1558 | 1593 | 7974 |
| 131072 | 10949 | 1660 | 1672 | 7792 |

No OOM encountered. Q8\_0 reduces the context allocation at full 131,072 tokens from 3,126 MiB
to 1,660 MiB, leaving **7,792 MiB free**.

Note: an earlier startup log appeared to show F16 caches regardless of the `--cache-type-k/v
q8_0` flags. The sweep data contradicts this — Q8\_0 produces a clear and consistent reduction
in context allocation across all measured sizes. The server log's apparent F16 report was
misleading; `--cache-type-k/v q8_0` is effective and should be used.

**F16 vs Q8\_0 comparison:**

| ctx-size | context F16 (MiB) | context Q8\_0 (MiB) | ratio |
| --- | --- | --- | --- |
| 8192 | 246 | 130 | 1.892× |
| 32768 | 822 | 436 | 1.885× |
| 65536 | 1590 | 844 | 1.884× |
| 98304 | 2358 | 1252 | 1.883× |
| 131072 | 3126 | 1660 | 1.883× |

The F16/Q8\_0 compression ratio is a consistent **~1.883×** — essentially identical to the
dense models (1.88×). The ratio converges from above as context grows: at small ctx-sizes the
fixed SWA cache (2,560 cells regardless of `--ctx-size`) inflates the apparent cost, pulling
the ratio upward; at large ctx-sizes the global KV cache dominates and the ratio asymptotes to
its true value.

**Per-token KV cache cost:**

The apparent MiB/token figures are non-linear for gpt-oss-20b, unlike the dense models, because
of the fixed-size SWA cache. The marginal cost is best read from the large-context end of the
sweep where the fixed component becomes negligible:

| Pass | Context at 131,072 tokens | Marginal MiB/token |
| --- | --- | --- |
| F16 | 3,126 MiB | **~0.0238** |
| Q8\_0 | 1,660 MiB | **~0.0127** |

These are far lower than any of the dense models, driven by compact per-head KV dimensions
(`n_embd_head_k/v = 64`) and GQA with 8 KV heads vs 64 query heads (`n_gqa = 8`).

**Cross-model KV cache comparison at maximum practical context:**

| Model | Max practical ctx | KV cache Q8\_0 (MiB) | KV MiB/token (Q8\_0) | Free VRAM (MiB) |
| --- | --- | --- | --- | --- |
| Devstral Q4\_K\_M | 98,304 | 8,160 | 0.083 | 531 |
| DeepSeek-R1-Distill-Qwen-14B Q6\_K\_L | 98,304 | 9,792 | 0.100 | 916 |
| gpt-oss-20b MXFP4 | 131,072 | 1,660 | 0.013 | 7,792 |

gpt-oss-20b achieves a 33% larger context window, a KV cache 5–6× smaller, and nearly 7.8 GiB
of free headroom at its ceiling — versus under 1 GiB for the dense models at theirs.


## 11\. Agent Frontend: OpenCode

OpenCode ([github.com/anomalyco/opencode](https://github.com/anomalyco/opencode)) is an open-source, provider-agnostic terminal coding agent. It is functionally analogous to Claude Code but decoupled from any specific model provider, MIT-licensed, and explicitly designed for local model use.

### 11.1 Key Capabilities

*   **Provider-agnostic:** Connects to any OpenAI-compatible endpoint. llama-server on localhost:8001 is a first-class configuration, documented explicitly in OpenCode's provider docs.
*   **Built-in agents:** Two default agents — `build` (full-access, default) and `plan` (read-only, for exploration). Tab-switches between them.
*   **LSP integration:** Language Server Protocol support out of the box, enabling semantic code intelligence beyond what the model alone provides.
*   **Session persistence:** Session metadata (title, timestamps) survives restarts and is queryable via `opencode session list`. Message content is not persisted to disk in v1.2.24 — see §11.7 for the chat export workaround.
*   **Client/server architecture:** The TUI is just one possible client. OpenCode can run on the workstation and be driven from a remote interface — useful for long autonomous sessions.
*   **Superpowers native:** OpenCode is one of the three platforms Superpowers explicitly supports with a dedicated integration path.

### 11.2 Installing OpenCode

#### Node.js prerequisite

OpenCode is distributed as an npm package. Debian 12 Bookworm ships Node.js 18.x, which reached end-of-life in April 2025 and is not recommended. Install Node.js 24 (current Active LTS, supported until April 2028) from the NodeSource repository instead.

Do **not** use `sudo apt install nodejs` — Debian's packaged version is too old.

**Add the NodeSource repository and install:**

```bash
curl -fsSL https://deb.nodesource.com/setup_24.x | sudo -E bash -
sudo apt-get install -y nodejs
```

The setup script adds the NodeSource apt repository and imports its GPG key. The subsequent `apt-get install` installs nodejs as a fully apt-tracked package, so it will receive updates via `apt upgrade` like any other package.

**Verify:**

```bash
node --version   # expect v24.x.x
npm --version    # expect 11.x.x
```

**Confirm apt is tracking the package:**

```bash
apt-cache policy nodejs
```

The output should show the installed version coming from `deb.nodesource.com/node_24.x`.

Note: the NVIDIA CUDA repository also ships its own version of `dkms` which apt may offer to upgrade. Use `apt-mark hold dkms` to prevent this if your current driver and kernel module are working correctly.

#### Install OpenCode

```bash
sudo npm install -g opencode-ai
```

If npm displays a notice that a newer version of itself is available, ignore it — the version bundled with Node.js 24 is current enough and updating npm separately can cause permission issues on Debian.

Or via the install script (does not require a separate Node.js installation):

```bash
curl -fsSL https://opencode.ai/install | bash
```

Verify the installation:

```bash
opencode --version
```

If this returns `command not found` despite the install succeeding, the global package directory has restrictive permissions (`750` instead of `755`). This is a known packaging defect with NodeSource's Node.js distribution on Debian: because NodeSource installs to a root-owned prefix, global npm installs require `sudo`, but running npm under sudo inherits root's more restrictive umask and produces directories that lock out normal users. A correctly packaged Debian nodejs would handle this transparently. Fix it with:

```bash
sudo chmod -R a+rX /usr/lib/node_modules/opencode-ai
```

Then re-run `opencode --version` to confirm.

### 11.3 Connecting OpenCode to llama-server

OpenCode is configured via `~/.config/opencode/opencode.json`. Add a provider entry pointing at the llama-server endpoint:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "local": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Local llama.cpp",
      "options": { "baseURL": "http://127.0.0.1:8001/v1" },
      "models": {
        "devstral": { "name": "mistralai_Devstral-Small-2-24B-Instruct-2512-Q4_K_M", "tools": true },
        "gpt-oss-20b": { "name": "openai_gpt-oss-20b-MXFP4", "tools": true },
        "deepseek-r1-14b": { "name": "DeepSeek-R1-Distill-Qwen-14B-Q6_K_L", "tools": true }
      }
    }
  }
}
```

The `"tools": true` declaration is required. A known failure mode with local models in OpenCode is tool calls silently not working because tool support is not declared in the provider config, even when the model and server support it correctly. This flag tells OpenCode to include tool definitions in the request payload.

The `"name"` field in each model entry must match the model ID that llama-server exposes via `/v1/models` — which is the GGUF filename stem (filename without the `.gguf` extension) when no `--alias` flag is passed to the server.

Only one model can be loaded in llama-server at a time. Switch the active model by restarting llama-server with a different `--model` path, then select the corresponding entry in OpenCode with `/models`.

**Select the model in OpenCode:**

```
opencode
# Then run: /models
# Select: local > gpt-oss-20b   (or devstral, or deepseek-r1-14b)
```

Or set a default in config:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "model": "local/gpt-oss-20b",
  "provider": {
    "local": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Local llama.cpp",
      "options": { "baseURL": "http://127.0.0.1:8001/v1" },
      "models": {
        "devstral": { "name": "mistralai_Devstral-Small-2-24B-Instruct-2512-Q4_K_M", "tools": true },
        "gpt-oss-20b": { "name": "openai_gpt-oss-20b-MXFP4", "tools": true },
        "deepseek-r1-14b": { "name": "DeepSeek-R1-Distill-Qwen-14B-Q6_K_L", "tools": true }
      }
    }
  }
}
```

### 11.4 Verifying the Integration

With llama-server running on port 8001, start OpenCode and confirm the model is reachable:

```
opencode
# Type a simple message — the model should respond
# Try: "list the files in this directory" — this triggers a tool call
# If tool calls work, the full agentic loop is functional
```

A working tool call confirms that llama-server's `--jinja` flag is active and OpenCode's `tools: true` is correctly configured. If responses come back but no tool calls execute, the most common causes are: missing `--jinja` in the server command, `tools: true` absent from the config, or context window set too low.

### 11.5 Known Issue: Jinja Role Alternation Error

**Symptom**

The first OpenCode request succeeds, but subsequent requests fail with an HTTP 500 error. The llama-server log shows:

```
Jinja Exception: After the optional system message, conversation roles must
alternate user and assistant roles except for tool calls and results.
```

After the first failure, llama-server falls back from `Chat format: jinja` to
`Chat format: peg-native`, which then also fails because peg-native cannot
handle Devstral's tool call format.

**Root cause**

OpenCode sends up to three separate system messages per request. Mistral's
Jinja chat template enforces strict role alternation and rejects this
structure at the template level. This is an OpenCode bug, not a llama-server
or model issue — Devstral works correctly when accessed via Mistral's own API,
which handles the message normalisation server-side.

The bug is tracked in OpenCode issue
[#5034](https://github.com/anomalyco/opencode/issues/5034). A fix has been
submitted as PR [#15018](https://github.com/anomalyco/opencode/pull/15018)
("For non-anthropic providers, combine system prompts"), which consolidates
multiple system messages into one before sending. As of the time of writing
the PR is open but not yet merged.

**Workaround: patched chat template**

Until the fix ships, the Jinja `raise_exception` calls that enforce role
alternation can be removed from the embedded chat template. llama-server will
then accept OpenCode's multi-system-message requests without error.

Step 1 — Extract the template from the GGUF:

```bash
python3 - <<'EOF'
import os
from gguf import GGUFReader

path = os.path.expanduser("~/gguf/mistralai_Devstral-Small-2-24B-Instruct-2512-Q4_K_M.gguf")
reader = GGUFReader(path, 'r')

for field in reader.fields.values():
    if field.name == "tokenizer.chat_template":
        template = bytes(field.parts[-1]).decode("utf-8")
        with open("/tmp/devstral_chat_template.jinja", "w") as f:
            f.write(template)
        print("Saved to /tmp/devstral_chat_template.jinja")
        break
EOF
```

(`pip install gguf --break-system-packages` if not already installed.)

Step 2 — Remove the two `raise_exception` lines from the template. The first
enforces role alternation:

```jinja
{%- if message["role"] == "user" != (ns.index % 2 == 0) -%}
{{- raise_exception("After the optional system message...") -}}  ← delete this line
{%- endif -%}
```

The second rejects unrecognised roles:

```jinja
{%- else -%}
{{- raise_exception("Only user, assistant and tool roles are supported...") -}}  ← delete this line
{%- endif -%}
```

Delete only the `raise_exception` lines; leave all surrounding `if`/`else`/`endif`
structure intact.

Step 3 — Save the patched template:

```bash
cp /tmp/devstral_chat_template.jinja ~/gguf/devstral_chat_template_patched.jinja
```

Step 4 — Add `--chat-template-file` to the llama-server command (see §11.6).

**Reverting the workaround**

Once PR #15018 (or equivalent) ships in a released version of OpenCode, remove
`--chat-template-file` from the server command and delete the patched template
file. The embedded template in the GGUF is unmodified and will resume being
used automatically.

### 11.6 Startup Script

Since llama-server must be running before OpenCode is launched, a simple wrapper is useful:

```
#!/bin/bash
# ~/bin/devstral

MODEL=~/gguf/mistralai_Devstral-Small-2-24B-Instruct-2512-Q4_K_M.gguf

# Start llama-server in background if not already running
if ! curl -s http://127.0.0.1:8001/health > /dev/null 2>&1; then
  echo "Starting llama-server..."
  llama-server \
    --model "$MODEL" \
    --n-gpu-layers 99 \
    --ctx-size 98304 \
    --cache-type-k q8_0 \
    --cache-type-v q8_0 \
    --flash-attn on \
    --jinja \
    --chat-template-file ~/gguf/devstral_chat_template_patched.jinja \
    --port 8001 \
    --host 127.0.0.1 &
  # Wait for server to be ready
  until curl -s http://127.0.0.1:8001/health > /dev/null 2>&1; do
    sleep 1
  done
  echo "llama-server ready."
fi

opencode "$@"
```

```
chmod +x ~/bin/devstral
```

This checks whether the server is already running before starting a new instance, passes through any arguments to OpenCode, and waits for the server to be healthy before launching the UI.

### 11.7 Exporting Chat Sessions

OpenCode has a native `/export` command that saves the current session as a markdown file. Run it from within a session:

```
/export
```

A dialogue appears with the following options:

- **Filename** — editable text field, defaults to `session-<session-id>.md`
- **Include thinking** — includes the model's reasoning traces, rendered as italicised `_Thinking:_` sections
- **Include tool details** — includes tool call inputs and outputs as fenced blocks
- **Include assistant metadata** — includes model name and response time per turn (e.g. `Build · gpt-oss-20b · 0.9s`)
- **Open without saving** — observed to have no effect in current testing

All three content checkboxes are enabled by default. Press return to confirm; the file is saved to the current working directory.

**Export format.** The exported markdown uses a consistent structure: session title and metadata at the top, then each turn as a `## User` or `## Assistant` heading. Assistant turns include a metadata line showing the agent mode, model, and response time. Thinking blocks appear inline as `_Thinking:_ ... text ...`. Tool calls appear as `**Tool: toolname**` with `**Input:**` and `**Output:**` subsections.

**Reasoning traces.** The `/export` command captures thinking blocks through OpenCode's own display layer, independently of llama-server's `--reasoning-format` flag. Reasoning traces appear in exports regardless of whether `--reasoning-format none` is set on the server. The `--reasoning-format none` flag remains useful for making reasoning visible in the live OpenCode UI during a session, but is not a prerequisite for reasoning to appear in exports.

## 12\. Workflow Framework: Superpowers

Superpowers ([github.com/obra/superpowers](https://github.com/obra/superpowers)) is an agentic skills framework and software development methodology that runs inside coding agents. It provides structured, automatic workflows that replace ad-hoc prompting with repeatable, high-quality engineering process.

### 12.1 How It Works

Superpowers defines a library of skills — structured instruction documents that the agent loads before relevant tasks. Skills are not manually invoked; they trigger automatically when the agent detects the appropriate context. The system enforces a development methodology, not merely provides tools.

**Skill injection mechanism:** Superpowers works by injecting the relevant skill markdown document into the agent's context window before each phase. The agent reads its instructions for that phase fresh from the skill document rather than relying on memory from the start of the session. This means the methodology stays active and precise across arbitrarily long sessions — the agent is re-grounded at each phase boundary rather than drifting from initial instructions.

From the moment a session starts and the agent detects that code is being built, the workflow activates automatically:

| # | Phase | Description |
| --- | --- | --- |
| 1 | Brainstorming | Agent asks clarifying questions to extract a precise spec. Does not write code first. |
| 2 | Git Worktrees | Creates an isolated branch and workspace. Verifies a clean test baseline before any changes. |
| 3 | Writing Plans | Breaks work into 2–5 minute tasks. Each task has exact file paths, complete code, and verification steps. |
| 4 | Subagent Execution | Dispatches a fresh subagent per task. Two-stage review: spec compliance, then code quality. |
| 5 | TDD Enforcement | RED-GREEN-REFACTOR cycle enforced. Code written before tests is deleted and rewritten. |
| 6 | Code Review | Review against plan between tasks. Critical issues block forward progress. |
| 7 | Branch Completion | Verifies tests, presents merge/PR/keep/discard options, cleans up worktree. |

**Relationship to planning:** Phase 3 is analogous to Claude Code's planning mode — the agent produces a concrete plan before any code is written, which can be reviewed before execution begins. The plan is not advisory: phase 6 reviews each completed task against the plan before proceeding, so the plan actively governs execution rather than drifting away as the session progresses.

**TDD enforcement:** The RED-GREEN-REFACTOR cycle is enforced mechanically, not by convention. If the agent writes implementation code before a failing test exists, that code is deleted and the task restarts. This is not recoverable by patching — the enforcement is structural.

**Scope:** Superpowers is designed around software engineering workflows. The brainstorming and planning phases would likely apply sensibly to documentation tasks, but phases like TDD enforcement and git worktree creation are code-specific. Whether the workflow degrades gracefully for non-code tasks should be verified by inspecting the skill documents in the Superpowers repository before relying on it for documentation work.

### 12.2 Installation on OpenCode

Superpowers installs globally into `~/.config/opencode/` and is active in every OpenCode session once installed. It does not require per-project setup.

**Installation** is performed by giving OpenCode the following prompt from any working directory:

```
Fetch and follow instructions from
https://raw.githubusercontent.com/obra/superpowers/refs/heads/main/.opencode/INSTALL.md
```

The model fetches the INSTALL.md and executes three steps:

1. Clones the Superpowers repository to `~/.config/opencode/superpowers/`
2. Creates a plugin symlink: `~/.config/opencode/plugins/superpowers.js` → `~/.config/opencode/superpowers/.opencode/plugins/superpowers.js`
3. Creates a skills symlink: `~/.config/opencode/skills/superpowers` → `~/.config/opencode/superpowers/skills`

**Empirical notes (verified with gpt-oss-20b MXFP4):**

During installation, OpenCode prompts for filesystem write and bash execution permission. These prompts must be accepted — declining them causes the install to fail silently. They are OpenCode's standard tool-use confirmation mechanism, not a security warning.

If the model fetches the URL but produces only a descriptive response without executing the steps, retry the prompt. The second attempt completes successfully.

**Verify installation** by checking all three components are in place:

```bash
ls ~/.config/opencode/superpowers/skills/
ls -l ~/.config/opencode/plugins/superpowers.js
ls -l ~/.config/opencode/skills/superpowers
```

The skills directory should contain all 14 skills. Both symlinks should resolve correctly.

**How it works.** The plugin (`superpowers.js`) uses OpenCode's `experimental.chat.system.transform` hook to inject the `using-superpowers` skill content directly into the system prompt at the start of every session. This means Superpowers is always active — no per-session invocation is needed, and no per-project installation is required. The `using-superpowers` skill instructs the model to load other skills via OpenCode's native `skill` tool before responding to any task.

**Skill priority.** Project-level skills in `.opencode/skills/` within a project directory take precedence over personal skills in `~/.config/opencode/skills/`, which take precedence over the global Superpowers skills. This allows per-project overrides without affecting the global installation.

**Updating Superpowers:**

```bash
cd ~/.config/opencode/superpowers
git pull
```

No restart or reinstall is needed after pulling — the plugin reads skill files from disk at session start.

### 12.3 Model Requirements and Fit

Superpowers is demanding on the model. Its workflow generates substantial system prompts (skill documents are loaded before tasks), requires reliable structured tool calls throughout long autonomous sessions, and dispatches subagents that must follow precise instructions without drift.

The preferred primary model for this stack — gpt-oss-20b MXFP4 — is confirmed to work with Superpowers. Its ~250 t/s generation speed and full 131K context window are well-matched to Superpowers' multi-phase autonomous sessions. Devstral-Small-2-24B Q4\_K\_M is also a strong fit given its purpose-training on agentic software engineering workflows (68% SWE-Bench Verified), though its ~55 t/s generation speed makes long autonomous sessions noticeably slower.

Sessions where Superpowers drives the agent autonomously for an hour or more are common and expected.

### 12.4 Context Window Management During Sessions

Superpowers manages context window growth through two mechanisms that prevent a single session from accumulating unbounded context.

**Fresh subagents per task:** Rather than one continuous conversation carrying all history forward, each task in phase 4 dispatches a fresh subagent. The subagent receives only what it needs: the relevant skill document, the plan for that specific task, and the files involved. Accumulated history from prior tasks does not carry forward into each new subagent's context. This is the primary architectural decision that makes multi-hour sessions tractable.

**Incremental file loading:** Files are loaded into context explicitly when needed and dropped when they are not. The full codebase is never held simultaneously.

The practical implication is that individual subagent context windows should remain well within the 98K ceiling even in long sessions. The Superpowers skill document overhead is estimated at 3–6K tokens per session. Empirical characterisation of actual context consumption across a full development session is identified as future work (see Section 16).

## 13\. Language Servers and MCP

OpenCode supports two distinct extensibility mechanisms that address different problems: Language Server Protocol (LSP) for deep semantic understanding of code, and Model Context Protocol (MCP) for connecting the agent to external capabilities and data sources. They are complementary — semantic code intelligence on one side, agentic reach on the other.

Neither language servers nor MCP servers consume GPU resources or VRAM. The GPU is used exclusively by llama-server during inference. Everything else in the stack — OpenCode, Superpowers, language servers, MCP servers, SearXNG — runs entirely on CPU and system RAM. Both can be added freely without any impact on the inference stack or available context window.

### 13.1 How OpenCode Communicates with Language Servers and MCP Servers: stdio IPC

Both language servers and MCP servers are spawned by OpenCode as child processes and communicate with it through stdio pipes — the standard input and standard output streams every Unix process has by default. OpenCode writes a JSON-encoded message into the child process's stdin; the server reads it, performs its work, and writes the result back to its own stdout; OpenCode reads that stdout. The OS wires up this pipe automatically at the moment the child process is spawned. No port number, no socket file, and no configuration are required.

This is inter-process communication (IPC) — the general term for mechanisms that allow separate processes to exchange data. The stdio pipe is the simplest IPC mechanism Unix provides. Both the MCP specification and the LSP specification support it as a transport, and it is the default for the language servers listed in §13.2 (`rust-analyzer`, `pyright`, `typescript-language-server`, `clangd`, `gopls`) as well as for all MCP servers configured in `opencode.json`. The tradeoff is scope: a stdio pipe only works between a parent process and a child it directly spawned. It cannot be shared across unrelated processes or across machines.

The distinction between LSP and MCP in this chapter is therefore not about how they communicate — both use stdio pipes in this stack — but about what they do: LSP provides semantic code intelligence, MCP provides external tool dispatch.

LSP does also support TCP as an alternative transport, used in configurations where a language server needs to be shared across multiple editor instances or run on a remote machine. None of the servers listed in §13.2 require this; it is noted here for completeness.

Other IPC mechanisms in common use have different tradeoffs:

**Unix domain sockets** use a socket file on the filesystem (e.g. `/var/run/docker.sock`). Any process with the appropriate filesystem permissions can connect — not just a parent/child pair — making them suitable for daemons that must accept connections from multiple unrelated clients. The Docker daemon uses a Unix domain socket to communicate with the `docker` CLI.

**TCP sockets** use an IP address and port number rather than a filesystem path. They carry the same socket abstraction as Unix domain sockets but can cross machine boundaries and are accessible from any process on the network. SearXNG uses a TCP socket — it listens on `http://127.0.0.1:8080` and accepts HTTP requests from any local process, including the `mcp-searxng` child process that OpenCode spawns.

**Shared memory and message queues** are lower-level kernel-managed IPC facilities used in performance-critical applications. They are not relevant to this stack.

The practical consequence of the stdio design shared by both LSP and MCP is that all server configuration in this stack is simply a process invocation — a command, arguments, and environment variables. OpenCode spawns each server when needed, communicates with it over the pipe for the duration of the session, and the process exits when the session ends. There is no daemon to manage and no port to allocate. For MCP servers that need to reach external services (as `mcp-searxng` reaches SearXNG over HTTP), that outbound TCP connection is the MCP server's own concern, invisible to OpenCode.

### 13.2 Language Servers (LSP)

A language server is a background process that maintains a live semantic model of your codebase. Where a plain file read gives the model text, a language server gives it meaning: symbol tables, type information, call graphs, and import resolution. The Language Server Protocol standardises communication so a single server implementation works with any compatible editor or agent.

OpenCode has LSP support built in. Language servers run as separate CPU processes and are queried by OpenCode when the agent needs semantic operations — go-to-definition, find all references, rename across project, type-aware completions, and real-time diagnostics. This provides a layer of code intelligence that is independent of what the model alone can infer from file contents. Resource usage is modest: `rust-analyzer` on a large Rust project may use 1–2 GB of system RAM and spike CPU during re-indexing; `pyright` and `clangd` are lighter. Between requests they are essentially idle.

Recommended language servers by language:

| Language | Server | Install |
| --- | --- | --- |
| Rust | rust-analyzer | `rustup component add rust-analyzer` |
| Python | pyright | `npm i -g pyright` |
| TypeScript / JavaScript | typescript-language-server | `npm i -g typescript-language-server` |
| C / C++ | clangd | `sudo apt install clangd` |
| Go | gopls | `go install golang.org/x/tools/gopls@latest` |
| Lua | lua-language-server | Via GitHub releases |
| Docker / Compose / Bake | docker-language-server | `go install github.com/docker/docker-language-server/cmd/docker-language-server@latest` |

Language servers are language-specific and stateful — each one maintains a persistent index of the project. They do not need configuration in OpenCode beyond ensuring the binary is on PATH; OpenCode detects and activates them automatically based on the file types in the current workspace.

**Note on Docker language servers:** `docker-language-server` is the official Docker-published server and covers Dockerfiles, Docker Compose files, and Bake files. An older alternative, `dockerfile-language-server` by rcjsuen (`npm i -g dockerfile-language-server-nodejs`), covers Dockerfiles only. The official server is the better choice for new installations. Both address file authoring only — syntax, completions, and diagnostics. Managing running containers at runtime requires an MCP server (see §13.8).

### 13.3 Third-Party Package Selection Criteria

> *Candidate for promotion to §4 (Software Stack Overview) as a general stack principle.*

When selecting a third-party MCP server — or any external package that will sit in a privileged position in the stack (spawned by the agent, receiving tool calls, running on localhost) — the selection should be grounded in concrete evidence of quality rather than proximity in search results. The same reasoning applied to GGUF quantizers in §8.2 applies here.

Positive signals to look for, in rough priority order:

**Community adoption** — Star and fork counts on GitHub are an imperfect but useful proxy. A package with 500+ stars and 80+ forks has been validated by a large enough population that systematic errors would have surfaced and been reported. A package with 12 stars may be perfectly good but offers no such evidence.

**Active maintenance** — Recent commits, a meaningful commit history, and responsiveness to issues indicate the package tracks upstream API changes. Stale packages break silently when dependencies shift.

**Test coverage** — The presence of a test suite, and a CI badge showing it passes, is evidence the author cares about correctness. MCP servers that mishandle tool call parsing or response formatting fail in ways that are difficult to diagnose from the agent side.

**Professional affiliation or track record** — An author with a verifiable professional background in the relevant domain, or a prior record of maintained packages, reduces abandonment risk. This is not a formal designation — it is earned trust, established through a public record of professional-quality work that others have validated over time.

**Licence** — MIT or Apache 2.0. Avoid packages with ambiguous, research-only, or non-commercial licences.

**Minimal footprint** — Prefer packages that do one thing and expose it over stdio. Packages that require persistent daemons, remote accounts, or non-local network access contradict the local-first principle of the stack.

When multiple packages satisfy these criteria, prefer the one with the highest community adoption as a tiebreaker — the community has done the comparative evaluation already.


### 13.4 Model Context Protocol (MCP)

MCP ([modelcontextprotocol.io](https://modelcontextprotocol.io)) is an open protocol that standardises how agents dispatch tool calls to external services. Where LSP answers questions about code semantics, MCP extends what the agent can _do_ — searching the web, reading a knowledge base, provisioning cloud infrastructure, or querying any service with an MCP server.

MCP servers are ordinary CPU processes — typically small Node.js or Python scripts — that communicate with OpenCode over stdio. They run entirely on the host CPU and system RAM, with negligible footprint: a few tens of MB of RAM and minimal CPU when actively handling a request, essentially idle between requests. The GPU is not involved; MCP servers complete their work before llama-server is invoked for the next generation step.

MCP servers are configured in OpenCode's `~/.config/opencode/opencode.json` under an `"mcp"` key. Each server is a process OpenCode spawns on demand, communicating over stdio.

**Conceptual configuration structure:**

```json
{
  "mcp": {
    "server-name": {
      "type": "local",
      "command": ["npx", "-y", "package-name"],
      "enabled": true,
      "environment": {
        "ENV_VAR": "value"
      }
    }
  }
}
```

The OpenCode MCP schema requires `"type": "local"` for stdio servers, `command` as an array (not a string), and environment variables under `"environment"` (not `"env"`).

**On-demand provisioning.** MCP servers configured with `["npx", "-y", "package-name"]` do not require a separate installation step and will not appear in `npm list -g`. The `npx -y` invocation fetches and runs the package on demand each time OpenCode spawns the server process. After the first run, npx caches the package in `~/.npm/_npx/` and uses the cached version on subsequent invocations unless a newer version is available. This applies to all `npx`-based MCP servers in this stack. Servers using `uvx` instead of `npx` follow the same pattern but cache in `~/.cache/uv/`.

### 13.5 Local Git Repository Access

`mcp-server-git` is the official reference implementation from the MCP project (`modelcontextprotocol/servers`). It operates entirely against on-disk repositories with no network calls, no external accounts, and no API keys. It is invoked via `uvx`, which handles on-demand fetching and caching identically to `npx` (see §13.4).

**Honest capability assessment.** OpenCode already has full bash access, so the agent can run `git log`, `git diff`, `git status`, and any other git command directly via its shell tool — and in practice it will. Empirically, a prompt as simple as `git status` results in the model invoking bash rather than the MCP server, which is the correct and more direct choice for simple operations. `mcp-server-git` provides the same operations with structured, parsed JSON output and injection-safe argument handling (validated arguments via process spawning rather than shell interpolation), which is meaningful when the agent needs to reason programmatically over structured repository data — parsing commit history, comparing branches, or processing diff output — rather than simply running a one-off git command. For an agent with full bash access, this is a modest quality-of-life improvement rather than a capability unlock. Its value is more pronounced in environments where bash is unavailable.

**Note on scope.** `mcp-server-git` operates on local repositories only. It does not interact with GitHub, GitLab, or any remote API. No MCP-level authentication is required.

#### 13.5.1 Prerequisites

`uvx` is provided by `uv`, a fast Python package and tool manager written in Rust, developed by Astral (the team behind the `ruff` linter). It is a drop-in replacement for `pip`, `pipx`, `virtualenv`, and related tools, and is 10–100× faster due to its Rust implementation and aggressive caching. `uvx` is `uv`'s equivalent of `npx`: it fetches a Python package from PyPI and runs it in an isolated ephemeral environment, caching to `~/.cache/uv/` after the first run.

There is no official Debian package from Astral. Install via the upstream standalone installer, which places binaries in `~/.local/bin/` with no root required:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Verify both binaries are on PATH:

```bash
uv --version
uvx --version
```

If either returns `command not found`, add `~/.local/bin` to PATH in `~/.bashrc`:

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

Updates are handled with `uv self update`. Removal is simply `rm ~/.local/bin/uv ~/.local/bin/uvx`.

#### 13.5.2 Verifying the Server

Before adding to OpenCode, confirm `mcp-server-git` starts correctly by sending a minimal MCP initialization message:

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"0.1"}}}' \
  | uvx mcp-server-git
```

Expected response (empirically confirmed, v1.26.0):

```json
{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2024-11-05","capabilities":{"experimental":{},"tools":{"listChanged":false}},"serverInfo":{"name":"mcp-git","version":"1.26.0"}}}
```

Note that the server identifies itself as `"mcp-git"` in the `serverInfo` field — this is what appears in OpenCode's `/mcp` panel, not `mcp-server-git`. The first run fetches and installs approximately 33 packages; subsequent runs use the `~/.cache/uv/` cache and start in milliseconds. As with all stdio MCP servers, the process blocks waiting for further input after responding — this is normal.

#### 13.5.3 OpenCode Configuration

Add the `git` entry to the `mcp` block in `~/.config/opencode/opencode.json`:

```json
{
  "mcp": {
    "git": {
      "type": "local",
      "command": ["uvx", "mcp-server-git"],
      "enabled": true
    }
  }
}
```

No environment variables are required. The server infers the repository from the current working directory when OpenCode spawns it.

**Verify in OpenCode:**

```
opencode
# Then: /mcp
```

The MCP panel should show `mcp-git connected`.


### 13.6 PostgreSQL

> **Status: stub.** This section will be completed when a PostgreSQL database is set up as part of a project. The configuration pattern and credential management approach are documented here for reference.

The recommended MCP server for local PostgreSQL access is `@modelcontextprotocol/server-postgres`, the official reference implementation from the MCP project. It provides read-only access — schema inspection and SELECT queries — with no risk of modifying data. Write access can be added later by switching to `crystaldba/postgres-mcp`, which supports configurable read/write access and adds performance analysis tools (explain plans, index tuning).

The connection string contains a password and must not be hardcoded in `opencode.json`. The same wrapper script pattern used for Trilium (§13.8.5) applies here: store the password in `pass`, construct the connection string at spawn time.

**Suggested `pass` entry:**

```bash
pass insert postgresql/myproject
```

**Wrapper script** (`~/.local/bin/postgres-mcp`):

```bash
#!/bin/bash
PG_PASS=$(pass show postgresql/myproject)
npx -y @modelcontextprotocol/server-postgres \
  "postgresql://username:${PG_PASS}@localhost:5432/mydb"
```

```bash
chmod +x ~/.local/bin/postgres-mcp
```

**OpenCode configuration:**

```json
{
  "mcp": {
    "postgres": {
      "type": "local",
      "command": ["postgres-mcp"],
      "enabled": true
    }
  }
}
```

This section should be updated with empirical startup output, confirmed server name and version, and any OpenCode-specific configuration findings once the database is set up.


### 13.7 Web Search via SearXNG

For a privacy-preserving web search capability, the recommended approach is a self-hosted SearXNG ([github.com/searxng/searxng](https://github.com/searxng/searxng)) instance paired with `mcp-searxng` as the MCP proxy. SearXNG runs as a Docker container and exposes a JSON search API on localhost — no external API keys or account required. `mcp-searxng` spawns as a stdio child process of OpenCode and translates tool calls into HTTP requests against the local SearXNG instance.

**Architecture:**

```
OpenCode ←—stdio—→ mcp-searxng ←—HTTP—→ SearXNG (Docker, TCP :8080)
```

**MCP server selection.** `ihor-sokoliuk/mcp-searxng` (npm package `mcp-searxng`) is the recommended proxy. It meets all package selection criteria from §13.3: 500+ stars, 80+ forks, active maintenance, MIT licence, stdio transport, single env var configuration, and no persistent daemon. It also provides URL content fetching with caching alongside the search tool.

#### 13.7.1 SearXNG Configuration

Create the config directory and settings file before starting the container:

```bash
mkdir -p ~/.config/searxng
cat > ~/.config/searxng/settings.yml << 'EOF'
use_default_settings: true

server:
  bind_address: "0.0.0.0"
  secret_key: "replace-with-output-of-openssl-rand-hex-32"
  limiter: false

search:
  safe_search: 0
  formats:
    - html
    - json
EOF
```

Generate a unique secret key:

```bash
openssl rand -hex 32
```

Replace the placeholder value in `settings.yml` with the output.

Two settings are required for programmatic localhost use: `limiter: false` disables the bot-detection rate limiter (which would block the MCP proxy's requests), and `json` must be explicitly listed under `formats` — it is not enabled by default and without it the `/search?format=json` endpoint returns a 403.

#### 13.7.2 Known Issue: IPv6 Disabled at Kernel Level

SearXNG releases from approximately early 2026 onwards switched from uWSGI to **granian** as the WSGI server. Granian unconditionally attempts to bind a dual-stack (IPv4+IPv6) socket on startup, which fails immediately with `RuntimeError: Address family not supported by protocol (os error 97)` on kernels where IPv6 is fully disabled via `ipv6.disable=1`.

The fix is to pass `GRANIAN_HOST=0.0.0.0` as a Docker environment variable. This tells granian to bind an IPv4-only socket, bypassing the dual-stack attempt entirely. The variable is passed through by SearXNG's container entrypoint — this is documented behaviour: `$GRANIAN_*` environment variables configure the granian server directly.

This workaround is required on this machine (IPv6 disabled at kernel level via GRUB parameter). It is not needed on machines with IPv6 enabled.

#### 13.7.3 Starting SearXNG

```bash
docker run -d \
  --name searxng \
  --restart unless-stopped \
  -p 127.0.0.1:8080:8080 \
  -v ~/.config/searxng:/etc/searxng \
  -e GRANIAN_HOST=0.0.0.0 \
  --user $(id -u):$(id -g) \
  searxng/searxng
```

`-p 127.0.0.1:8080:8080` binds the container port to the loopback interface only — the service is not reachable from other machines on the network.

`--restart unless-stopped` ensures SearXNG starts automatically with Docker after a reboot.

`--user $(id -u):$(id -g)` runs the container process as your host uid:gid rather than the container's internal `searxng` user (uid 977). Without this flag, the container entrypoint runs `chown` on its mounted volumes at startup, silently taking ownership of `~/.config/searxng/` away from your user on every container start. The flag prevents this. The `Permission denied` log line for `/etc/ssl/certs/ca-certificates.crt.new` is a cosmetic consequence — the cert update script cannot write to a root-owned path inside the container — but the existing CA bundle is already present and SearXNG operates correctly.

**Verify the container started correctly:**

```bash
docker logs searxng 2>&1 | tail -10
```

Expected output includes:

```
[INFO] Starting granian (main PID: 1)
[INFO] Listening at: http://0.0.0.0:8080
[INFO] Spawning worker-1 with PID: ...
[INFO] Started worker-1
```

`Listening at: http://0.0.0.0:8080` confirms granian bound IPv4-only. If the log instead shows `http://:::8080`, the IPv6 workaround did not take effect.

The `ahmia` and `torch` engine failures logged at startup are cosmetic — these are onion/darknet search engines that require a Tor proxy. The missing `limiter.toml` warning is also cosmetic and only relevant for public instances.

**Verify the JSON search API responds:**

```bash
curl -s 'http://127.0.0.1:8080/search?q=llama.cpp&format=json' | python3 -m json.tool | head -20
```

A response with a `results` array containing real web results confirms the instance is operational.

#### 13.7.4 OpenCode Configuration

Add the `mcp` block to `~/.config/opencode/opencode.json`. The OpenCode MCP schema requires `"type": "local"`, `command` as an array, and environment variables under `"environment"` (not `"env"`):

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "local": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Local llama.cpp",
      "options": { "baseURL": "http://127.0.0.1:8001/v1" },
      "models": {
        "devstral": { "name": "devstral-small-2-24b-instruct-2512-q4_k_m", "tools": true },
        "gpt-oss-20b": { "name": "gpt-oss-20b", "tools": true },
        "deepseek-r1-14b": { "name": "DeepSeek-R1-Distill-Qwen-14B-Q6_K_L", "tools": true }
      }
    }
  },
  "mcp": {
    "searxng": {
      "type": "local",
      "command": ["npx", "-y", "mcp-searxng"],
      "enabled": true,
      "environment": {
        "SEARXNG_URL": "http://127.0.0.1:8080"
      }
    }
  }
}
```

`mcp-searxng` requires no separate installation — it is fetched and cached by npx on first use, as described in §13.4.

**Verify in OpenCode:**

```
opencode
# Then: /mcp
```

The MCP panel should show `searxng connected / enabled`. The server exposes two tools: `search` (web search via SearXNG) and `fetch_url` (URL content retrieval with caching).

### 13.8 Trilium Notes

For access to a local TriliumNext personal knowledge base, `trilium-bolt` ([github.com/mursilsayed/trilium-bolt](https://github.com/mursilsayed/trilium-bolt)) is the recommended MCP server. It automatically converts TriliumNext's internal HTML note storage to markdown before returning content to the model, which results in cleaner token usage and better model comprehension compared to raw HTML injection.

`trilium-bolt` exposes the following operations: full-text search and attribute-based note queries, retrieving notes by ID with content and metadata, navigating note hierarchy, creating new notes, updating note titles and content, and deleting notes.

**Markdown conversion:** No explicit export command or conversion step is needed. When the agent retrieves a note, the content arrives as markdown — the HTML-to-markdown conversion is transparent and automatic. A workflow like "get the note titled X and save it as `X.md` in the current directory" works directly: `trilium-bolt` handles retrieval and conversion, and the agent uses its own file tools for the write.

This section covers TriliumNext installed from the official `.deb` package (desktop Electron app), which exposes the ETAPI on port 37840. The server-only build uses port 8080 instead.

#### 13.8.1 TriliumNext Installation

The official `.deb` release is available from the TriliumNext GitHub releases page:

```
https://github.com/TriliumNext/Trilium/releases
```

Install in the usual way:

```bash
sudo dpkg -i TriliumNotes-vX.Y.Z-linux-x64.deb
sudo apt-get install -f   # resolve any missing dependencies
```

Verify the installation:

```bash
dpkg -s trilium
```

TriliumNext stores its data in `~/.local/share/trilium-data/` — the SQLite database, backups, logs, and session state all live there.

#### 13.8.2 Confirming ETAPI is Running

When TriliumNext is running as a desktop application, its ETAPI server listens on port 37840. Confirm it is active:

```bash
ss -tlnp | grep 37840
```

Expected output:

```
LISTEN 0  511  0.0.0.0:37840  0.0.0.0:*  users:(("trilium",pid=XXXXXX,fd=104))
```

If the port is not listed, TriliumNext is not running. Start it from the application launcher or:

```bash
trilium &
```

#### 13.8.3 Generating an ETAPI Token

In the TriliumNext UI: **Menu → Options → ETAPI → Create new ETAPI token**

Give the token a descriptive name (e.g. `opencode-mcp`). Copy the token immediately — it is only shown once.

#### 13.8.4 Storing the Token in pass

The ETAPI token should be stored in `pass` rather than hardcoded in any config file. Following the service-first naming convention:

```bash
pass insert trilium/etapi
```

Enter the token when prompted. It is stored encrypted at `~/.password-store/trilium/etapi.gpg`.

Retrieve and verify:

```bash
pass show trilium/etapi
```

#### 13.8.5 Wrapper Script

`opencode.json` is static JSON with no shell expansion support. The clean solution for injecting a `pass`-managed secret is a small wrapper script that retrieves the token at spawn time.

Create `~/.local/bin/trilium-bolt-mcp`:

```bash
#!/bin/bash
TRILIUM_TOKEN=$(pass show trilium/etapi) \
TRILIUM_URL=http://localhost:37840 \
npx -y trilium-bolt
```

Make it executable:

```bash
chmod +x ~/.local/bin/trilium-bolt-mcp
```

Two environment variables are required: `TRILIUM_TOKEN` is the ETAPI authentication token, and `TRILIUM_URL` must point to `http://localhost:37840` for the desktop app build. The default assumed by trilium-bolt's documentation is port 8080, which is the server-only build — this will fail silently with the desktop app unless explicitly overridden.

**Verify the wrapper end-to-end** by sending a minimal MCP initialization message:

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"0.1"}}}' \
  | ~/.local/bin/trilium-bolt-mcp
```

Expected response:

```json
{"result":{"protocolVersion":"2024-11-05","capabilities":{"tools":{"listChanged":true}},"serverInfo":{"name":"trilium-bolt","version":"1.4.0"}},"jsonrpc":"2.0","id":1}
```

A response containing `serverInfo` with `name: trilium-bolt` confirms the token is valid, the ETAPI is reachable, and the wrapper is correct. If the process simply blocks without output, that is also normal — MCP servers block waiting for stdin input; the test above forces an immediate response by piping a message in.

#### 13.8.6 OpenCode Configuration

Add the `trilium` entry to the `mcp` block in `~/.config/opencode/opencode.json`. OpenCode inherits the user's `$PATH` when spawning MCP child processes, so a bare command name works and is more portable than a hardcoded absolute path:

```json
{
  "mcp": {
    "trilium": {
      "type": "local",
      "command": ["trilium-bolt-mcp"],
      "enabled": true
    }
  }
}
```

No `environment` block is needed — the token and URL are injected by the wrapper script itself.

**Path handling note.** JSON has no shell expansion, so `~/` is treated as a literal string rather than expanding to the home directory. A path like `~/.local/bin/trilium-bolt-mcp` in the `command` array will fail silently. Use either the bare command name (if the script is on `$PATH`) or a fully-qualified absolute path (e.g. `/home/user/.local/bin/trilium-bolt-mcp`).

**Verify in OpenCode:**

```
opencode
# Then: /mcp
```

The MCP panel should show `trilium connected`. Test the integration with a live query:

```
Search my Trilium notes for "test"
```

A response drawing on actual note content confirms the full round-trip is functional.

### 13.9 AWS

AWS publishes an official open-source MCP suite at `awslabs/mcp` ([github.com/awslabs/mcp](https://github.com/awslabs/mcp)). For a privacy-preserving local configuration, the open-source stdio-based servers are appropriate — credentials stay on the local machine and are never routed through AWS-hosted infrastructure.

The suite includes specialised servers for individual services (CDK, S3, CloudWatch, EKS, ECS, cost analysis) as well as a unified AWS MCP Server that consolidates documentation access, API execution across 15,000+ AWS APIs, and pre-built Agent SOPs for common multi-step tasks.

Authentication uses standard AWS IAM credentials. The recommended approach is SSO-based dynamic credentials rather than static access keys.

```json
{
  "mcp": {
    "aws-kb": {
      "command": "npx",
      "args": ["-y", "@aws/aws-mcp-servers"],
      "env": {
        "AWS_PROFILE": "your-profile",
        "AWS_REGION": "eu-west-1"
      }
    }
  }
}
```

All AWS MCP server actions are logged to CloudTrail, providing an audit trail for any infrastructure operations the agent performs.

### 13.10 Docker Container Management

Managing running Docker containers requires an MCP server rather than a language server. The Docker language server (§13.2) addresses file authoring only; container lifecycle operations — starting, stopping, inspecting, reading logs, managing Compose stacks — require a runtime connection to the Docker daemon via MCP.

Three options are available at different levels of scope and setup complexity.

**`docker-mcp` by QuantGeekDev** ([github.com/QuantGeekDev/docker-mcp](https://github.com/QuantGeekDev/docker-mcp)) — The simplest path. Supports container creation, Docker Compose stack deployment, log retrieval, and container listing and status monitoring. Requires `uv` to be installed on the system. No persistent daemon:

```json
{
  "mcp": {
    "docker": {
      "command": "uvx",
      "args": ["docker-mcp"]
    }
  }
}
```

**Comprehensive Docker MCP server** — Exposes 33 Docker tools covering container, image, network, volume, and system management. Includes a three-tier safety classification (safe / moderate / destructive) with confirmation required before destructive operations execute. This safety property is meaningful when an agent is driving container operations autonomously during a Superpowers session.

**Docker MCP Toolkit (official)** — Docker's own MCP Gateway infrastructure, which acts as a centralised proxy managing multiple MCP servers, credentials, and lifecycle. Docker's documentation explicitly lists OpenCode as a supported client. The OpenCode configuration entry is:

```json
{
  "mcp": {
    "MCP_DOCKER": {
      "type": "local",
      "command": ["docker", "mcp", "gateway", "run"],
      "enabled": true
    }
  }
}
```

The Toolkit approach is more involved to set up but provides access to Docker's full curated catalog of verified MCP servers beyond Docker management alone — Stripe, Grafana, Elastic, and others are available through the same gateway. For the immediate goal of container management only, `docker-mcp` is the quickest path.

## 14\. Performance: Memory Bandwidth

### 14.0 Background: Generation and Prefill

A language model processes text as a sequence of tokens — integer IDs representing words,
subwords, or characters. When asked to produce a response, the model works in two distinct
phases.

**Prefill** processes the entire input in a single forward pass: the user's message, the
system prompt, any tool results, and the full conversation history. Every input token is
processed simultaneously, in parallel, across all layers of the model. The output of prefill
is the KV cache — a record of the attention keys and values for every input token, which must
be retained in VRAM for the duration of the response. Prefill is compute-bound: the GPU's
Tensor Cores are the primary bottleneck, and throughput scales with both prompt length and
available compute. This is why prefill is measured in thousands of tokens per second.

**Autoregressive generation** (decode) produces the response one token at a time. To generate
each new token, the model runs a full forward pass through every layer, attending to the KV
cache of all previous tokens. No parallelism is available across tokens — each token depends
on the one before it, so they must be produced sequentially. Each forward pass reads the
entire active weight set from VRAM, processes it through the GPU's compute units, and produces
a single token. The compute work per token is small; the bottleneck is the time spent
streaming weights from VRAM. This makes generation memory-bandwidth-bound, with throughput
governed by:

```
tokens/sec  ≈  memory_bandwidth (GB/s)  ÷  active_weight_size (GB)
```

For dense models (Devstral, DeepSeek), all parameters are active per token, so
`active_weight_size` equals the full model file size. For MoE models (gpt-oss-20b), only the
expert subset is active per token — gpt-oss-20b activates ~3.6B of 20.91B parameters,
meaning its effective weight per token is far smaller than the 11.27 GiB file size implies.
This is why gpt-oss-20b generates ~250 t/s on the RTX 4090 while Devstral generates ~55 t/s,
despite similar file sizes.

Because the formula produces materially different results per model, estimated t/s figures for
other GPUs are only meaningful when tied to a specific model and validated against empirical
data. The hardware characteristics table below shows bandwidth and VRAM only; for measured
performance figures see §14.2 (gpt-oss-20b cross-hardware comparison) and §14.6 (cross-model
summary on the RTX 4090).

| Card | VRAM | Bandwidth | Notes |
| --- | --- | --- | --- |
| **RTX 4090 (current)** | 24GB GDDR6X | 1,008 GB/s | Empirical results in §14.1–§14.7 |
| RTX 5090 | 32GB GDDR7 | 1,792 GB/s | 1.78× bandwidth; gpt-oss-20b results in §14.2 |
| RTX PRO 6000 Blackwell | 96GB GDDR7 ECC | 1,792 GB/s | 1.78× bandwidth; gpt-oss-20b results in §14.2 |
| RTX 6000 Ada | 48GB GDDR6 ECC | 960 GB/s | ~5% less bandwidth than RTX 4090 |
| RTX A6000 | 48GB GDDR6 ECC | 768 GB/s | ~24% less bandwidth than RTX 4090 |


### 14.1 llama-bench Results: RTX 4090, gpt-oss-20b-MXFP4

> **Note:** All llama-bench figures in §14.1–§14.3 are from single runs. llama-bench reports
> within-run variance (±) but does not capture run-to-run variance. A statistically robust
> repeat study (§14.4) is planned before these figures are treated as definitive or submitted
> for external comparison.

The `llama-bench` command and parameters are taken from the llama.cpp official guide at
`github.com/ggml-org/llama.cpp/discussions/15396`. The bench tests two ubatch sizes (2048 and
4096) at four prompt sizes (2048, 8192, 16384, 32768 tokens) plus text generation at 128 tokens.
Results were posted to the guide discussion at:
`github.com/ggml-org/llama.cpp/discussions/15396#discussioncomment-16063223`

**Command (original — ub 2048/4096):**

```bash
llama-bench \
  -m ~/gguf/openai_gpt-oss-20b-MXFP4.gguf \
  -t 1 -fa 1 -b 4096 -ub 2048,4096 \
  -p 2048,8192,16384,32768
```

**Results (RTX 4090, build 8244, CUDA 13.0, single run):**

| model | size | params | backend | ngl | n\_batch | n\_ubatch | fa | test | t/s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gpt-oss 20B MXFP4 MoE | 11.27 GiB | 20.91 B | CUDA | 99 | 4096 | 2048 | 1 | pp2048 | 10365.85 ± 22.61 |
| gpt-oss 20B MXFP4 MoE | 11.27 GiB | 20.91 B | CUDA | 99 | 4096 | 2048 | 1 | pp8192 | 10480.32 ± 11.00 |
| gpt-oss 20B MXFP4 MoE | 11.27 GiB | 20.91 B | CUDA | 99 | 4096 | 2048 | 1 | pp16384 | 9883.74 ± 8.01 |
| gpt-oss 20B MXFP4 MoE | 11.27 GiB | 20.91 B | CUDA | 99 | 4096 | 2048 | 1 | pp32768 | 8516.20 ± 316.75 |
| gpt-oss 20B MXFP4 MoE | 11.27 GiB | 20.91 B | CUDA | 99 | 4096 | 2048 | 1 | tg128 | 254.63 ± 0.74 |
| gpt-oss 20B MXFP4 MoE | 11.27 GiB | 20.91 B | CUDA | 99 | 4096 | 4096 | 1 | pp2048 | 10346.03 ± 50.50 |
| gpt-oss 20B MXFP4 MoE | 11.27 GiB | 20.91 B | CUDA | 99 | 4096 | 4096 | 1 | pp8192 | 9478.60 ± 20.41 |
| gpt-oss 20B MXFP4 MoE | 11.27 GiB | 20.91 B | CUDA | 99 | 4096 | 4096 | 1 | pp16384 | 9227.06 ± 3.65 |
| gpt-oss 20B MXFP4 MoE | 11.27 GiB | 20.91 B | CUDA | 99 | 4096 | 4096 | 1 | pp32768 | 8297.05 ± 9.71 |
| gpt-oss 20B MXFP4 MoE | 11.27 GiB | 20.91 B | CUDA | 99 | 4096 | 4096 | 1 | tg128 | 254.76 ± 0.59 |

**Command (tuned — b=4096 ub=1024, adopted standard):**

```bash
llama-bench \
  -m ~/gguf/openai_gpt-oss-20b-MXFP4.gguf \
  -ngl 99 -t 1 -fa 1 \
  -b 4096 -ub 1024 \
  -p 2048,8192,16384,32768 \
  -n 128,256,512,1024,2048,4096
```

**Results (RTX 4090, build 8244, CUDA 13.0, single run):**

| model | size | params | backend | ngl | n\_batch | n\_ubatch | fa | test | t/s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gpt-oss 20B MXFP4 MoE | 11.27 GiB | 20.91 B | CUDA | 99 | 4096 | 1024 | 1 | pp2048 | 11167.01 ± 39.90 |
| gpt-oss 20B MXFP4 MoE | 11.27 GiB | 20.91 B | CUDA | 99 | 4096 | 1024 | 1 | pp8192 | 10851.27 ± 22.53 |
| gpt-oss 20B MXFP4 MoE | 11.27 GiB | 20.91 B | CUDA | 99 | 4096 | 1024 | 1 | pp16384 | 10173.66 ± 19.70 |
| gpt-oss 20B MXFP4 MoE | 11.27 GiB | 20.91 B | CUDA | 99 | 4096 | 1024 | 1 | pp32768 | 8857.26 ± 44.99 |
| gpt-oss 20B MXFP4 MoE | 11.27 GiB | 20.91 B | CUDA | 99 | 4096 | 1024 | 1 | tg128 | 255.28 ± 0.93 |
| gpt-oss 20B MXFP4 MoE | 11.27 GiB | 20.91 B | CUDA | 99 | 4096 | 1024 | 1 | tg256 | 254.74 ± 1.34 |
| gpt-oss 20B MXFP4 MoE | 11.27 GiB | 20.91 B | CUDA | 99 | 4096 | 1024 | 1 | tg512 | 250.64 ± 1.95 |
| gpt-oss 20B MXFP4 MoE | 11.27 GiB | 20.91 B | CUDA | 99 | 4096 | 1024 | 1 | tg1024 | 249.66 ± 1.36 |
| gpt-oss 20B MXFP4 MoE | 11.27 GiB | 20.91 B | CUDA | 99 | 4096 | 1024 | 1 | tg2048 | 246.58 ± 2.76 |
| gpt-oss 20B MXFP4 MoE | 11.27 GiB | 20.91 B | CUDA | 99 | 4096 | 1024 | 1 | tg4096 | 227.11 ± 14.54 |

The tuned run shows higher prefill figures across all prompt sizes (+4–8%) compared to the
original run. Whether this reflects a genuine effect of `-ub 1024` or run-to-run variance
cannot be determined from single runs; the repeat study in §14.4 is needed to resolve this.

**Observations:**

At ubatch 2048, prefill peaks at **pp8192 (10,480 t/s)** — slightly higher than pp2048 (10,366
t/s). This is unexpected; typically prefill speed decreases with prompt length as attention cost
grows. The likely explanation is that at pp2048, the batch is too small to fully saturate the
GPU's Tensor Cores; at pp8192, each ubatch tile delivers more parallelism and the throughput
climbs before attention overhead begins to dominate at larger sizes. At ubatch 4096, the pp2048
batch is large enough to saturate from the start, so the peak is at pp2048 (10,346 t/s) with a
monotonic decline thereafter.

Generation speed for Devstral Q4\_K\_M on the same hardware is ~53–55 t/s. The gpt-oss-20b
MoE architecture, with only 3.6B active parameters per token despite 20.91B total parameters,
moves approximately 4.7× less weight per generated token — yielding the ~4.7× generation
speedup observed (254 vs 53 t/s).


### 14.2 Cross-Hardware Comparison: gpt-oss-20b-MXFP4 (CUDA, n\_ubatch=2048)

Reference benchmarks from the official llama.cpp guide (build 6210, CUDA 12.6), plus local
RTX 4090 result (build 8244, CUDA 13.0) which has been submitted to the guide discussion.
All runs use `-t 1 -fa 1 -b 4096 -ub 2048`. Note: subsequent local testing (§14.3) confirms
ub is not a meaningful variable for decode; `-ub 1024` is now the adopted standard.

| GPU | VRAM | pp2048 (t/s) | pp8192 (t/s) | pp16384 (t/s) | pp32768 (t/s) | tg128 (t/s) | build |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **RTX 4090 (submitted to guide)** | 24GB | **10,366** | **10,480** | **9,884** | **8,516** | **255** | **8244** |
| RTX 4090 (guide) | 24GB | 8,022 | 7,265 | 6,298 | 5,112 | 222 | 6210 |
| RTX 5090 (guide) | 32GB | 9,848 | 8,834 | 7,802 | 6,291 | 283 | 6210 |
| RTX PRO 6000 Blackwell (guide) | 96GB | 11,522 | 10,673 | 9,772 | 8,267 | 287 | 6205 |
| RTX PRO 6000 Max-Q (guide) | 96GB | 9,481 | 8,922 | 8,196 | 7,050 | 250 | 6199 |
| RTX 3090 (guide) | 24GB | 5,171 | 4,772 | 4,289 | 3,577 | 162 | 6210 |

The submitted RTX 4090 result (build 8244 / CUDA 13.0) outperforms the guide's existing RTX
4090 entry (build 6210 / CUDA 12.6) by approximately **29% on pp2048** and **44% on pp8192**,
and **15% on generation**. This reflects llama.cpp improvements over the ~34-build delta. It
also notably surpasses the RTX 5090 on prefill, and comes within ~10% of the RTX PRO 6000
Blackwell on prefill while matching it on generation — both cards that are much more expensive
and carry far more VRAM.

The RTX PRO 6000 Blackwell retains a meaningful generation advantage only at tg128 (287 vs 255
t/s, +12%), where its higher memory bandwidth (1,792 vs 1,008 GB/s) is the binding constraint.
Its primary advantage for this workload is not speed but capacity: 96GB enables gpt-oss-120b
and much larger context windows.


### 14.3 Decode Batch Size Sweep: gpt-oss-20b-MXFP4 (RTX 4090, build 8244)

A focused sweep was run to determine whether `-b` and `-ub` are meaningful variables for
single-user decode performance. Prefill was disabled (`-p 0`) to isolate pure generation.

```bash
llama-bench -m ~/gguf/openai_gpt-oss-20b-MXFP4.gguf \
  -ngl 99 -t 1 -fa 1 -p 0 \
  -n 128,256,512,1024,2048,4096 \
  -b 1024,2048,4096 \
  -ub 1024,2048,4096
```

This produced 54 data points: 9 batch configurations × 6 generation lengths.

**Results summary (t/s) — b=4096:**

| n_ubatch | tg128 | tg256 | tg512 | tg1024 | tg2048 | tg4096 |
| --- | --- | --- | --- | --- | --- | --- |
| 1024 | 257.93 ± 0.59 | 257.89 ± 0.33 | 251.68 ± 4.72 | 249.43 ± 4.75 | 245.97 ± 5.27 | 239.27 ± 7.95 |
| 2048 | 256.93 ± 1.54 | 246.45 ± 10.47 | 252.56 ± 1.09 | 242.69 ± 8.40 | 240.09 ± 5.59 | 244.18 ± 1.36 |
| 4096 | 257.66 ± 0.64 | 255.80 ± 2.79 | 254.65 ± 0.36 | 253.04 ± 0.11 | 247.37 ± 4.27 | 235.23 ± 2.23 |

**Key findings:**

*   **Batch size is not a meaningful variable for decode.** All 54 data points fall within a
    239–258 t/s band. No configuration produces a statistically distinguishable improvement
    over any other once error bars are accounted for.
*   **At b=4096, ub has no effect.** All three ub values (1024, 2048, 4096) produce results
    within each other's error bars at every generation length.
*   **b=2048 is consistently the weakest setting** across all ub values and generation lengths,
    but the differences remain within noise — this is likely a scheduling artefact rather than
    a meaningful effect.
*   **Generation speed decays gently with sequence length** (~18–22 t/s from tg128 to tg4096
    across all configurations). This reflects the growing KV cache that must be read alongside
    model weights on every decode step — an expected and consistent bandwidth cost.
*   **tg128 shows the tightest error bars** across all configurations. This is likely an
    artefact of small sample size: fewer tokens generated means less opportunity for variance
    to accumulate, rather than a genuine stability property of any particular b/ub setting.

**Conclusion:** `-b 4096 -ub 1024` is adopted as the standard server configuration. The choice
is principled (best mean at tg128, tightest error bars) but the practical difference versus any
other configuration is negligible. Decode speed on the RTX 4090 is bound by the 1,008 GB/s
memory bandwidth ceiling; no batch configuration can change this.


### 14.4 Planned: Repeat Study for Statistical Robustness

All benchmark figures in §14.1–§14.3 are from single llama-bench runs. llama-bench reports
within-run variance (±) from its internal repetitions, but does not capture run-to-run
variance — which, as the tg4096 figures across §14.1 and §14.3 illustrate (239 vs 227 t/s),
can be substantial. Single-run figures should be treated as indicative rather than definitive.

A repeat study of ~30 runs is planned to establish means and confidence intervals for each
test cell, and to determine whether the prefill improvement observed at `-ub 1024` vs `-ub 2048`
in §14.1 is a genuine effect or run-to-run noise.

**Planned command (to be run ~30 times overnight):**

```bash
llama-bench \
  -m ~/gguf/openai_gpt-oss-20b-MXFP4.gguf \
  -ngl 99 -t 1 -fa 1 \
  -b 4096 -ub 1024 \
  -p 2048,8192,16384,32768 \
  -n 128,256,512,1024,2048,4096 \
  -o jsonl >> ~/logs/llama-bench-gpt-oss-20b-repeat.jsonl
```

**Wrapper script:**

```bash
#!/bin/bash
OUT=~/logs/llama-bench-gpt-oss-20b-$(date '+%Y%m%d_%H%M%S').jsonl
for i in $(seq 1 30); do
    echo "=== Run $i ===" >&2
    llama-bench \
      -m ~/gguf/openai_gpt-oss-20b-MXFP4.gguf \
      -ngl 99 -t 1 -fa 1 \
      -b 4096 -ub 1024 \
      -p 2048,8192,16384,32768 \
      -n 128,256,512,1024,2048,4096 \
      -o jsonl >> "$OUT" 2>/dev/null
done
```

JSONL output allows straightforward post-processing: group by `test` field, compute mean and
standard deviation across the 30 samples per cell, and derive confidence intervals. Results
will replace the single-run figures in §14.1 once the study is complete.


### 14.5 llama-bench Results: RTX 4090, DeepSeek-R1-Distill-Qwen-14B-Q6\_K\_L

> **Note:** Single run; same caveats as §14.1 apply. The high within-run variance on pp2048
> (±272 t/s) is a signal that run-to-run variance will also be significant for this model.

**Command:**

```bash
llama-bench \
  -m ~/gguf/DeepSeek-R1-Distill-Qwen-14B-Q6_K_L.gguf \
  -t 1 -fa 1 -b 4096 -ub 1024 \
  -p 2048,8192,16384,32768 \
  -n 128,256,512,1024,2048,4096
```

**Results (RTX 4090, build 8244, CUDA 13.0, single run):**

| model | size | params | backend | ngl | n\_batch | n\_ubatch | fa | test | t/s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| qwen2 14B Q6\_K | 11.64 GiB | 14.77 B | CUDA | 99 | 4096 | 1024 | 1 | pp2048 | 5245.17 ± 272.55 |
| qwen2 14B Q6\_K | 11.64 GiB | 14.77 B | CUDA | 99 | 4096 | 1024 | 1 | pp8192 | 4516.48 ± 161.07 |
| qwen2 14B Q6\_K | 11.64 GiB | 14.77 B | CUDA | 99 | 4096 | 1024 | 1 | pp16384 | 4009.72 ± 65.64 |
| qwen2 14B Q6\_K | 11.64 GiB | 14.77 B | CUDA | 99 | 4096 | 1024 | 1 | pp32768 | 3049.10 ± 61.29 |
| qwen2 14B Q6\_K | 11.64 GiB | 14.77 B | CUDA | 99 | 4096 | 1024 | 1 | tg128 | 70.02 ± 0.41 |
| qwen2 14B Q6\_K | 11.64 GiB | 14.77 B | CUDA | 99 | 4096 | 1024 | 1 | tg256 | 68.67 ± 2.48 |
| qwen2 14B Q6\_K | 11.64 GiB | 14.77 B | CUDA | 99 | 4096 | 1024 | 1 | tg512 | 63.90 ± 4.55 |
| qwen2 14B Q6\_K | 11.64 GiB | 14.77 B | CUDA | 99 | 4096 | 1024 | 1 | tg1024 | 60.58 ± 1.98 |
| qwen2 14B Q6\_K | 11.64 GiB | 14.77 B | CUDA | 99 | 4096 | 1024 | 1 | tg2048 | 66.22 ± 1.89 |
| qwen2 14B Q6\_K | 11.64 GiB | 14.77 B | CUDA | 99 | 4096 | 1024 | 1 | tg4096 | 65.97 ± 2.70 |

**Observations:**

Prefill peaks at pp2048 (~5,245 t/s) and declines steeply to ~3,049 t/s at pp32768 — a 42%
fall. This is significantly steeper than gpt-oss-20b's 21% fall over the same range, consistent
with dense full-attention scaling quadratically with sequence length. gpt-oss-20b's hybrid SWA
architecture limits attention cost for most layers and partly accounts for its much higher
prefill throughput.

Generation at tg128 (~70 t/s) is faster than Devstral (~55 t/s) despite Q6\_K being a
heavier quantisation than Q4\_K\_M. This is expected: 14.77B parameters move less weight per
token than Devstral's 23.6B, so the bandwidth-bound generation ceiling is higher. The
theoretical ceiling is approximately 1,008 GB/s ÷ 11.64 GiB ≈ 84 t/s; ~70 t/s at tg128
represents reasonable efficiency.

The tg decay pattern shows an anomalous recovery at tg2048 (66.22) and tg4096 (65.97) after
the expected decline through tg1024 (60.58). This is likely noise from a single run given the
elevated within-run variance observed on the prefill tests; the repeat study methodology from
§14.4 should be applied to this model before drawing firm conclusions.


### 14.6 Cross-Model Performance Summary: RTX 4090, build 8244

All figures from single llama-bench runs; see §14.4 for planned repeat study.

| Metric | gpt-oss-20b MXFP4 | DeepSeek-R1-14B Q6\_K\_L | Devstral-24B Q4\_K\_M |
| --- | --- | --- | --- |
| Architecture | MoE (3.6B active / 20.91B total) | Dense (14.77B) | Dense (23.57B) |
| File size | 11.27 GiB | 11.64 GiB | 13.34 GiB |
| Max practical ctx | 131,072 tokens | 98,304 tokens | 98,304 tokens |
| pp2048 (t/s) | 11,167 | 5,245 | 3,836 |
| pp8192 (t/s) | 10,851 | 4,516 | 3,638 |
| pp32768 (t/s) | 8,857 | 3,049 | 2,975 |
| Prefill decline pp2048→pp32768 | 21% | 42% | 22% |
| tg128 (t/s) | 255 | 70 | 57 |
| tg4096 (t/s) | 227 | 66 | 51 |
| BW efficiency at tg128 | ~37% (MoE active ~3.8 GiB) | ~83% | ~78% |
| Chain-of-thought reasoning | Yes (`<think>`) | Yes (`<think>`) | No |
| OpenCode tool calls verified | Yes | Pending | Yes (with patch) |

The gpt-oss-20b MoE architecture dominates on every measured dimension: larger context,
faster prefill, and ~4.5× faster generation than Devstral. The generation advantage is a
direct consequence of activating only 3.6B parameters per token — the bandwidth efficiency
figure appears low (~37%) precisely because the denominator is the full 11.27 GiB file, while
only ~3.8 GiB of active weights are read per token in practice.

The two dense models show almost identical prefill decline curves (21–22%) across the pp2048→
pp32768 range, consistent with standard quadratic attention scaling. DeepSeek's steeper 42%
decline likely reflects its larger KV head dimensions (1,024 MiB/token vs Devstral's lower
per-token cost) amplifying attention overhead at longer sequences. DeepSeek generates ~23%
faster than Devstral at tg128 (70 vs 57 t/s) because its 14.77B active parameters move less
weight per token than Devstral's 23.57B, despite the heavier Q6\_K quantisation.


### 14.7 llama-bench Results: RTX 4090, Devstral-Small-2-24B-Instruct-2512-Q4\_K\_M

> **Note:** Single run; same caveats as §14.1 apply. Error bars are consistently tight,
> suggesting lower run-to-run variance for this model than DeepSeek.

**Command:**

```bash
llama-bench \
  -m ~/gguf/mistralai_Devstral-Small-2-24B-Instruct-2512-Q4_K_M.gguf \
  -t 1 -fa 1 -b 4096 -ub 1024 \
  -p 2048,8192,16384,32768 \
  -n 128,256,512,1024,2048,4096
```

**Results (RTX 4090, build 8244, CUDA 13.0, single run):**

| model | size | params | backend | ngl | n\_batch | n\_ubatch | fa | test | t/s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mistral3 14B Q4\_K - Medium | 13.34 GiB | 23.57 B | CUDA | 99 | 4096 | 1024 | 1 | pp2048 | 3835.89 ± 37.23 |
| mistral3 14B Q4\_K - Medium | 13.34 GiB | 23.57 B | CUDA | 99 | 4096 | 1024 | 1 | pp8192 | 3638.12 ± 38.42 |
| mistral3 14B Q4\_K - Medium | 13.34 GiB | 23.57 B | CUDA | 99 | 4096 | 1024 | 1 | pp16384 | 3375.65 ± 15.21 |
| mistral3 14B Q4\_K - Medium | 13.34 GiB | 23.57 B | CUDA | 99 | 4096 | 1024 | 1 | pp32768 | 2975.22 ± 15.22 |
| mistral3 14B Q4\_K - Medium | 13.34 GiB | 23.57 B | CUDA | 99 | 4096 | 1024 | 1 | tg128 | 57.27 ± 4.01 |
| mistral3 14B Q4\_K - Medium | 13.34 GiB | 23.57 B | CUDA | 99 | 4096 | 1024 | 1 | tg256 | 57.38 ± 3.11 |
| mistral3 14B Q4\_K - Medium | 13.34 GiB | 23.57 B | CUDA | 99 | 4096 | 1024 | 1 | tg512 | 55.78 ± 0.82 |
| mistral3 14B Q4\_K - Medium | 13.34 GiB | 23.57 B | CUDA | 99 | 4096 | 1024 | 1 | tg1024 | 54.61 ± 1.63 |
| mistral3 14B Q4\_K - Medium | 13.34 GiB | 23.57 B | CUDA | 99 | 4096 | 1024 | 1 | tg2048 | 54.62 ± 0.26 |
| mistral3 14B Q4\_K - Medium | 13.34 GiB | 23.57 B | CUDA | 99 | 4096 | 1024 | 1 | tg4096 | 51.04 ± 1.25 |

> **Note on model label:** llama-bench reports this model as "mistral3 14B Q4\_K - Medium".
> The `mistral3` identifier reflects the architecture as registered in the GGUF metadata;
> the `14B` label reflects the quantised layer count visible to llama.cpp, not the full
> 23.57B parameter count. This is the correct GGUF for Devstral-Small-2-24B-Instruct-2512.

**Observations:**

Generation is flat from tg128 (57.27) through tg2048 (54.62), with a modest drop at tg4096
(51.04) — consistent with the expected gradual KV cache growth penalty on a dense model.
Error bars are tight throughout (≤4.01), suggesting stable and reproducible results; the
within-run variance is lower than observed for DeepSeek.

The theoretical generation ceiling is 1,008 GB/s ÷ 13.34 GiB ≈ 73 t/s; ~57 t/s at tg128
represents ~78% memory bandwidth efficiency. Prefill declines 22% from pp2048 to pp32768,
almost identical to gpt-oss-20b's 21%, consistent with both using standard full-attention
at comparable layer counts.

## 15\. GPU Upgrade Analysis

### 15.1 Candidate Cards

| Card | VRAM | Bandwidth | Price (Newegg) | ECC |
| --- | --- | --- | --- | --- |
| RTX 4090 (current) | 24GB GDDR6X | 1,008 GB/s | Owned | No |
| RTX 5090 | 32GB GDDR7 | 1,792 GB/s | ~$2,400–$4,500 | No |
| RTX 6000 Ada | 48GB GDDR6 ECC | 960 GB/s | ~$6,800 | Yes |
| RTX A6000 | 48GB GDDR6 ECC | 768 GB/s | ~$5,000–$6,500 | Yes |
| **RTX PRO 6000 Blackwell** | **96GB GDDR7 ECC** | **1,792 GB/s** | **~$8,240–$8,999** | **Yes** |

Context window capacity is model-dependent and covered in §10. The primary constraint on the
current RTX 4090 is VRAM for dense models (Devstral, DeepSeek) rather than for gpt-oss-20b,
which fits its full 131K context comfortably on 24GB.

### 15.2 Analysis

*   **RTX 6000 Ada and RTX A6000:** Bandwidth equal to or below the current RTX 4090. Generation speed does not improve despite higher prices. The VRAM gain is only meaningful for larger models or Q8 quality at long context. Poor value for this use case.
*   **RTX 5090:** Genuine 1.78× bandwidth improvement (1,792 GB/s). Generation speed scales proportionally for bandwidth-bound workloads. 32GB enables larger models and higher quantisation at long context. Best value upgrade path.
*   **RTX PRO 6000 Blackwell:** Matches the 5090's bandwidth while providing 96GB GDDR7 ECC. Enables Q8 quality at full context for all current models, and opens access to larger models such as gpt-oss-120b. ECC memory eliminates the risk of silent bit errors during multi-hour Superpowers sessions.

### 15.3 Recommendation

For the stated priorities — quality-first, long context, extended autonomous sessions:

*   **RTX PRO 6000 Blackwell (~$8,240–$8,999):** The architecturally correct single-card solution. Q8 quality at full context with ECC. Eliminates the VRAM constraint entirely and enables larger models.
*   **RTX 5090 (~$2,400–$4,500):** Value alternative. Identical bandwidth to PRO 6000; 32GB limits headroom for larger models and Q8 at long context. No ECC.

Staying on the RTX 4090 is a fully viable working configuration for most development tasks with the current model stack. An upgrade makes the most material difference for: Q8 quality preference, sustained multi-hour autonomous Superpowers sessions, and access to larger models.

## 16\. Why Multi-GPU Is Not Recommended

Adding a second consumer GPU does not provide a viable path to better inference performance for this use case.

### 16.1 The PCIe Bottleneck

Multi-GPU inference requires tensor parallelism: weight matrices are split across both cards, and each forward pass requires synchronisation across the PCIe bus at every layer boundary — hundreds of times per token generated.

| Interconnect | Bandwidth | Notes |
| --- | --- | --- |
| GDDR6X VRAM (intra-GPU) | 1,008 GB/s | ~100 ns latency |
| PCIe 4.0 x16 (inter-GPU) | ~32 GB/s | 31× slower than VRAM; ~1–2 µs latency |
| PCIe 4.0 x8/x8 (shared slot) | ~16 GB/s | 62× slower than VRAM; ~2–4 µs latency |
| NVLink (datacenter cards only) | 600–900 GB/s | ~200 ns; not available on consumer cards |

PCIe is 31× slower than VRAM bandwidth. Without NVLink — which consumer cards do not support — each added card introduces a per-token latency tax. Generation speed with dual 4090s typically equals or regresses compared to a single card.

### 16.2 Practical Outcomes

*   **Dual RTX 4090:** Devstral Q4 already fits on one card. A second card adds context capacity but generation speed likely regresses due to PCIe overhead.
*   **Four-way RTX 3090:** PCIe overhead compounds with each additional GPU. Near-linear degradation per card added.
*   **RTX PRO 6000 Blackwell:** Solves VRAM capacity, bandwidth, and ECC simultaneously on a single die. No inter-card communication overhead. The architectural advantage that justifies its price premium over any multi-GPU consumer setup.

## 17\. Future Work: Superpowers Context Consumption Study

The empirical VRAM study (companion document) characterised the hardware ceiling with precision. The natural follow-on is to characterise how a real Superpowers session consumes that budget over time.

The fresh-subagent architecture is designed to prevent unbounded context accumulation, but the actual consumption pattern across a multi-hour session has not been measured. Specific questions to address:

*   Context window size at each subagent dispatch across a representative development session
*   Whether individual subagent windows stay well within the 98K ceiling in practice
*   The point, if any, at which a very long session begins to approach the limit
*   Comparison of context consumption across task types: small feature, large refactor, test generation, debugging

The goal is to replace the current estimated 3–6K token skill overhead figure with empirically grounded measurements, giving the design document the same level of precision for Superpowers sessions that the VRAM study provides for hardware limits. Results should be documented in the same format as the VRAM study for direct comparability.

## 18\. Design Principle: Code Should Fit a Context Window

The context window makes concrete a principle with deep roots in software engineering:

> _A well-designed module should be fully comprehensible — its interface, implementation, and tests — within a single context window._

This is not a workaround for an AI limitation — it is a restatement of principles good engineers have articulated for decades, now made viscerally concrete by the context window.

### 18.1 Established Antecedents

*   **Dijkstra:** Programs should be understandable by a reader holding only bounded context in mind (human working memory: 7±2 chunks). The context window is a more precise, measurable version of this constraint.
*   **Single Responsibility Principle:** One thing per module means a small mental model. Context-window-sized modules are SRP-compliant by construction.
*   **Cognitive complexity metrics:** Low scores (SonarQube and equivalents) correlate directly with fitting inside a bounded context window.
*   **Unix philosophy:** Small programs that do one thing well and compose cleanly. Each program fits in one person's head — and one context window.
*   **Screaming architecture:** The top-level structure should immediately convey what the system does, enabling navigation without reading everything.

### 18.2 Practical Corollaries

*   **Shallow dependency graphs:** Deep coupling fills context with dependencies before any logic is read. Minimise transitive loading requirements.
*   **Interfaces as compression:** A well-designed interface summarises a component. Load the interface to reason about usage; load the implementation only when needed.
*   **Explicit over implicit:** Global state and action-at-a-distance force loading more context to understand any one piece. Explicit data flow keeps units self-contained.
*   **Tests as specifications:** A complete test suite compresses module behaviour without requiring the implementation. Tests are context-efficient proxies for full modules.

What the context window surfaces is that comprehensibility and correctness are related. Code that cannot be held in bounded context cannot be reliably reasoned about — by a human, by an AI, or by the original author returning to it months later. Bugs live in the gaps between what a reader can hold simultaneously. The context window did not create this constraint; it made it impossible to ignore.

## 19\. Summary

The complete recommended configuration for a quality-first, privacy-preserving, single-user AI coding agent on a Debian 12 workstation with an RTX 4090:

| Decision | Choice | Rationale |
| --- | --- | --- |
| Primary model | openai\_gpt-oss-20b MXFP4 | ~3× faster generation; full 131K context fits easily; chain-of-thought reasoning; no OpenCode compatibility issues |
| Alternate model | Devstral-Small-2-24B Q4\_K\_M | Purpose-trained for agentic coding (68% SWE-Bench); worth retaining for comparison |
| Inference server | llama.cpp llama-server | Required for `--jinja` (tool calls); OpenAI-compatible API; full CUDA acceleration |
| Agent frontend | OpenCode | Provider-agnostic; LSP; native Superpowers integration; MIT license |
| Workflow framework | Superpowers | TDD enforcement; subagent orchestration; automatic skill activation |
| Language servers | Per-language (rust-analyzer, pyright, docker-language-server, etc.) | Semantic code intelligence; CPU only; no GPU impact |
| Web search MCP | SearXNG (self-hosted) + local proxy | Fully local; no API keys; first-class tool call integration |
| Notes MCP | trilium-bolt | Automatic HTML-to-markdown; note retrieval, creation, search; on-demand; no daemon |
| Docker MCP | docker-mcp (quickstart) or Docker MCP Toolkit (full catalog) | Container and Compose management; CPU only; no GPU impact |
| AWS MCP | awslabs/mcp (stdio, open-source) | Local credentials; CloudTrail audit logging; 15,000+ APIs |
| GPU upgrade (recommended) | RTX PRO 6000 Blackwell | 96GB ECC; 1,792 GB/s; both models at full context and Q8 quality; single die |
| GPU upgrade (value) | RTX 5090 | 1.78× bandwidth; 32GB; headroom for larger models |

**Model selection rationale.** gpt-oss-20b MXFP4 is the preferred primary model based on
empirical testing. Its MoE architecture (3.6B active parameters out of 20.9B total) delivers
approximately 3× higher generation throughput and 2.5× higher prefill throughput than Devstral
on the same hardware. Its full 131,072-token context window fits within the RTX 4090's VRAM with
over 6GB to spare — no careful context budgeting required. Native chain-of-thought reasoning via
the harmony format is active by default. Critically, it works with OpenCode out of the box,
whereas Devstral requires a patched chat template as a workaround for an open OpenCode bug
(§11.5).

Devstral remains available in the OpenCode config and is worth retaining. It was purpose-trained
on agentic software engineering workflows and its 68% SWE-Bench Verified score reflects genuine
coding specialisation. Whether that specialisation translates to meaningfully better outcomes than
gpt-oss-20b's general reasoning capability in practice requires longer-term comparison across
real tasks.

_The RTX 4090 is a fully viable and productive working configuration today. Language servers and
MCP servers run entirely on CPU and can be added incrementally without any impact on the inference
stack. An upgrade to the RTX PRO 6000 Blackwell removes the VRAM ceiling entirely, enabling both
models at full context and Q8 quality for long autonomous Superpowers sessions._
