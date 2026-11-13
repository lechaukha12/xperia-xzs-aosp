#define _GNU_SOURCE
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <grp.h>
#include <linux/reboot.h>
#include <sched.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/klog.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/sysmacros.h>
#include <sys/types.h>
#include <time.h>
#include <unistd.h>

static void write_all(int fd, const void *buf, size_t n) {
    const char *p = (const char *)buf;
    while (n > 0) {
        ssize_t w = write(fd, p, n);
        if (w <= 0) break;
        p += w;
        n -= (size_t)w;
    }
}

static void klog_msg(const char *fmt, const char *arg, int rc) {
    int fd = open("/dev/kmsg", O_WRONLY | O_CLOEXEC);
    if (fd >= 0) {
        char buf[512];
        int n = snprintf(buf, sizeof(buf), fmt, arg ? arg : "", rc);
        if (n > 0) write_all(fd, buf, (size_t)n);
        close(fd);
    }
}

static void mkdirs_0755(const char *path) {
    char tmp[256];
    snprintf(tmp, sizeof(tmp), "%s", path);
    for (char *p = tmp + 1; *p; p++) {
        if (*p == '/') {
            *p = 0;
            mkdir(tmp, 0755);
            *p = '/';
        }
    }
    mkdir(tmp, 0755);
}

static void parse_and_mknod_uevent(const char *uevent_path, int is_char) {
    int fd = open(uevent_path, O_RDONLY | O_CLOEXEC);
    if (fd < 0) return;
    char buf[1024];
    int r = (int)read(fd, buf, sizeof(buf) - 1);
    close(fd);
    if (r <= 0) return;
    buf[r] = 0;

    int major = -1, minor = -1;
    char devname[128] = {0};
    char partname[128] = {0};

    char *save = NULL;
    for (char *line = strtok_r(buf, "\n", &save); line; line = strtok_r(NULL, "\n", &save)) {
        if (strncmp(line, "MAJOR=", 6) == 0) major = atoi(line + 6);
        else if (strncmp(line, "MINOR=", 6) == 0) minor = atoi(line + 6);
        else if (strncmp(line, "DEVNAME=", 8) == 0) snprintf(devname, sizeof(devname), "%s", line + 8);
        else if (strncmp(line, "PARTNAME=", 9) == 0) snprintf(partname, sizeof(partname), "%s", line + 9);
    }
    if (major < 0 || minor < 0 || !devname[0]) return;

    if (is_char) {
        char cpath[160];
        snprintf(cpath, sizeof(cpath), "/dev/%s", devname);
        unlink(cpath);
        mknod(cpath, S_IFCHR | 0660, makedev(major, minor));
        return;
    }

    char bpath[160];
    snprintf(bpath, sizeof(bpath), "/dev/block/%s", devname);
    unlink(bpath);
    mknod(bpath, S_IFBLK | 0600, makedev(major, minor));

    if (partname[0]) {
        const char *dirs[] = {
            "/dev/block/platform/soc/7464900.sdhci/by-name",
            "/dev/block/by-name",
            NULL
        };
        for (int i = 0; dirs[i]; i++) {
            mkdirs_0755(dirs[i]);
            char lpath[256];
            snprintf(lpath, sizeof(lpath), "%s/%s", dirs[i], partname);
            unlink(lpath);
            if (symlink(bpath, lpath) < 0) {}
        }
    }
}

static void populate_emmc_nodes(void) {
    for (int wait_i = 0; wait_i < 100; wait_i++) {
        if (access("/sys/block/mmcblk0/mmcblk0p55/uevent", R_OK) == 0) break;
        usleep(100000);
    }
    mkdirs_0755("/dev/block/platform/soc/7464900.sdhci/by-name");
    unlink("/dev/block/bootdevice");
    if (symlink("/dev/block/platform/soc/7464900.sdhci", "/dev/block/bootdevice") < 0) {}
    parse_and_mknod_uevent("/sys/block/mmcblk0/uevent", 0);
    DIR *d = opendir("/sys/block/mmcblk0");
    if (d) {
        struct dirent *de;
        while ((de = readdir(d)) != NULL) {
            if (strncmp(de->d_name, "mmcblk0p", 8) == 0) {
                char up[512];
                snprintf(up, sizeof(up), "/sys/block/mmcblk0/%s/uevent", de->d_name);
                parse_and_mknod_uevent(up, 0);
            }
        }
        closedir(d);
    }
    parse_and_mknod_uevent("/sys/bus/mmc/devices/mmc0:0001/mmcblk0rpmb/uevent", 1);
    if (chown("/dev/mmcblk0rpmb", 0, 1000) < 0) {}
    chmod("/dev/mmcblk0rpmb", 0660);
    unlink("/dev/block/mmcblk0rpmb");
    if (symlink("/dev/mmcblk0rpmb", "/dev/block/mmcblk0rpmb") < 0) {}
}

static void start_enforce_shadow_keeper(int enf_fd) {
    if (enf_fd < 0) return;
    pid_t pid = fork();
    if (pid != 0) {
        close(enf_fd);
        return;
    }
    setsid();
    for (int i = 0; i < 12000; i++) { // 60 seconds @ 5ms
        char c = 0;
        if (pread(enf_fd, &c, 1, 0) != 1 || c != '0') {
            if (pwrite(enf_fd, "0", 1, 0) < 0) {}
            if (ftruncate(enf_fd, 1) < 0) {}
        }
        usleep(5000);
    }
    close(enf_fd);
    _exit(0);
}

#ifdef DIAG_STAGE0
struct log_hdr {
    char magic[8];
    uint32_t tick;
    uint32_t kmsg_len;
    uint32_t proc_len;
    uint32_t reserved;
};

static uint32_t snapshot_procs(char *out, size_t cap) {
    size_t pos = 0;
    pos += (size_t)snprintf(out + pos, cap - pos, "=== /proc/mounts ===\n");
    int mfd = open("/proc/mounts", O_RDONLY | O_CLOEXEC);
    if (mfd >= 0) {
        int r = (int)read(mfd, out + pos, 8192);
        if (r > 0) pos += (size_t)r;
        close(mfd);
    }
    pos += (size_t)snprintf(out + pos, cap - pos, "\n=== processes ===\n");
    DIR *d = opendir("/proc");
    if (d) {
        struct dirent *de;
        while ((de = readdir(d)) != NULL && pos < cap - 512) {
            if (de->d_name[0] < '0' || de->d_name[0] > '9') continue;
            char cp[512], cmd[256] = {0}, st[256] = {0};
            snprintf(cp, sizeof(cp), "/proc/%s/cmdline", de->d_name);
            int fd = open(cp, O_RDONLY | O_CLOEXEC);
            if (fd >= 0) {
                int r = (int)read(fd, cmd, sizeof(cmd) - 1);
                close(fd);
                for (int k = 0; k < r; k++) if (cmd[k] == 0) cmd[k] = ' ';
            }
            snprintf(cp, sizeof(cp), "/proc/%s/wchan", de->d_name);
            fd = open(cp, O_RDONLY | O_CLOEXEC);
            if (fd >= 0) {
                int r = (int)read(fd, st, sizeof(st) - 1);
                if (r > 0) st[r] = 0;
                close(fd);
            }
            pos += (size_t)snprintf(out + pos, cap - pos, "PID %s [%s]: %s\n", de->d_name, st, cmd);
        }
        closedir(d);
    }
    return (uint32_t)pos;
}

static void write_p50_snapshot(int blk_fd, uint32_t tick, int do_procs) {
    static char payload[1024 * 1024]; // 1 MB max
    static char full_kbuf[2 * 1024 * 1024];
    static char pbuf[128 * 1024];

    int kn = klogctl(3, full_kbuf, sizeof(full_kbuf));
    if (kn < 0) kn = 0;
    const char *kptr = full_kbuf;
    if (kn > 768 * 1024) {
        kptr = full_kbuf + (kn - 768 * 1024);
        kn = 768 * 1024;
    }
    uint32_t pn = do_procs ? snapshot_procs(pbuf, sizeof(pbuf) - 1) : 0;

    struct log_hdr hdr;
    memcpy(hdr.magic, "A17LOG01", 8);
    hdr.tick = tick;
    hdr.kmsg_len = (uint32_t)kn;
    hdr.proc_len = pn;
    hdr.reserved = 0;

    size_t total = sizeof(hdr) + (size_t)kn + (size_t)pn;
    size_t aligned = (total + 4095) & ~((size_t)4095);
    if (aligned <= sizeof(payload)) {
        memset(payload + total, 0, aligned - total);
        memcpy(payload, &hdr, sizeof(hdr));
        if (kn > 0) memcpy(payload + sizeof(hdr), kptr, (size_t)kn);
        if (pn > 0) memcpy(payload + sizeof(hdr) + (size_t)kn, pbuf, (size_t)pn);
        if (pwrite(blk_fd, payload, aligned, 1024 * 1024) < 0) {}
    }
}

static void start_diag_logger(int blk_fd) {
    if (blk_fd < 0) return;
    write_p50_snapshot(blk_fd, 0, 1);

    pid_t pid = fork();
    if (pid != 0) {
        close(blk_fd);
        return;
    }

    setsid();
    for (uint32_t tick = 1; tick <= 480; tick++) { // 120s @ 250ms
        usleep(250000);
        if (access("/cache/.keep_alive", F_OK) == 0 ||
            access("/data/local/tmp/.keep_alive", F_OK) == 0) {
            klog_msg("<6>stage0_diag: .keep_alive detected! Exiting safety timer%s (%d)\n", "", 0);
            write_p50_snapshot(blk_fd, tick, 1);
            close(blk_fd);
            _exit(0);
        }
        write_p50_snapshot(blk_fd, tick, (tick % 8 == 0) ? 1 : 0);
    }

    klog_msg("<3>stage0_diag: 120s diagnostic window elapsed without .keep_alive; rebooting to TWRP%s (%d)\n", "", 0);
    write_p50_snapshot(blk_fd, 999, 1);
    fsync(blk_fd);
    close(blk_fd);
    sync();
    syscall(SYS_reboot, LINUX_REBOOT_MAGIC1, LINUX_REBOOT_MAGIC2, LINUX_REBOOT_CMD_RESTART2, "");
    _exit(0);
}
#endif

int main(int argc, char **argv) {
    if (argc > 1) {
        execv("/system/bin/init", argv);
        return 1;
    }

    umask(0);
    clearenv();
    setenv("PATH", "/product/bin:/apex/com.android.runtime/bin:/apex/com.android.art/bin:/system_ext/bin:/system/bin:/system/xbin:/odm/bin:/vendor/bin:/vendor/xbin", 1);

    struct timespec ts = {0, 0};
    clock_gettime(CLOCK_BOOTTIME, &ts);
    char started_ms[32];
    snprintf(started_ms, sizeof(started_ms), "%lld",
             (long long)ts.tv_sec * 1000LL + (long long)(ts.tv_nsec / 1000000LL));
    setenv("FIRST_STAGE_STARTED_AT", started_ms, 1);

    mkdir("/dev", 0755);
    mkdir("/proc", 0755);
    mkdir("/sys", 0755);
    mkdir("/mnt", 0755);
    mkdir("/metadata", 0775);
    mkdir("/debug_ramdisk", 0755);
    mkdir("/second_stage_resources", 0755);

    mount("tmpfs", "/dev", "tmpfs", MS_NOSUID, "mode=0755");
    mkdir("/dev/pts", 0755);
    mkdir("/dev/socket", 0755);
    mkdir("/dev/dm-user", 0755);
    mkdir("/dev/block", 0755);
    mount("devpts", "/dev/pts", "devpts", 0, NULL);

    mount("proc", "/proc", "proc", 0, "hidepid=2,gid=3009");
    chmod("/proc/cmdline", 0440);
    chmod("/proc/bootconfig", 0440);
    gid_t groups[] = { 3009 };
    setgroups(1, groups);

    mount("sysfs", "/sys", "sysfs", 0, NULL);
    mount("selinuxfs", "/sys/fs/selinux", "selinuxfs", 0, NULL);
    int enf_fd = open("/dev/.selinux_enforce_shadow", O_RDWR | O_CREAT | O_TRUNC | O_CLOEXEC, 0644);
    if (enf_fd >= 0) {
        write_all(enf_fd, "0", 1);
        mount("/dev/.selinux_enforce_shadow", "/sys/fs/selinux/enforce", NULL, MS_BIND, NULL);
    }

    mknod("/dev/kmsg", S_IFCHR | 0600, makedev(1, 11));
    mknod("/dev/kmsg_debug", S_IFCHR | 0622, makedev(1, 11));
    mknod("/dev/null", S_IFCHR | 0666, makedev(1, 3));
    mknod("/dev/zero", S_IFCHR | 0666, makedev(1, 5));
    mknod("/dev/ptmx", S_IFCHR | 0666, makedev(5, 2));
    mknod("/dev/random", S_IFCHR | 0666, makedev(1, 8));
    mknod("/dev/urandom", S_IFCHR | 0666, makedev(1, 9));

    int null_fd = open("/dev/null", O_RDWR);
    if (null_fd >= 0) {
        dup2(null_fd, 0);
        dup2(null_fd, 1);
        dup2(null_fd, 2);
        if (null_fd > 2) close(null_fd);
    }

    klog_msg("<6>init: keyaki_first_stage_init starting (boot_ms=%s, rc=%d)\n", started_ms, 0);

    mount("tmpfs", "/mnt", "tmpfs", MS_NOEXEC | MS_NOSUID | MS_NODEV, "mode=0755,uid=0,gid=1000");
    mkdir("/mnt/vendor", 0755);
    mkdir("/mnt/product", 0755);
    mount("tmpfs", "/metadata", "tmpfs", MS_NOEXEC | MS_NOSUID | MS_NODEV, "mode=0775,uid=0,gid=1000");
    mount("tmpfs", "/debug_ramdisk", "tmpfs", MS_NOEXEC | MS_NOSUID | MS_NODEV, "mode=0755,uid=0,gid=0");
    mount("tmpfs", "/second_stage_resources", "tmpfs", MS_NOEXEC | MS_NOSUID | MS_NODEV, "mode=0755,uid=0,gid=0");
    mkdirs_0755("/second_stage_resources/system/etc/ramdisk");
    int pfd = open("/second_stage_resources/system/etc/ramdisk/build.prop", O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0644);
    if (pfd >= 0) {
        const char *prop = "ro.boot.dynamic_partitions=false\n";
        write_all(pfd, prop, strlen(prop));
        close(pfd);
    }

    populate_emmc_nodes();

#ifdef DIAG_STAGE0
    int diag_blk_fd = open("/dev/block/mmcblk0p50", O_RDWR | O_DSYNC | O_CLOEXEC);
    if (diag_blk_fd >= 0) {
        write_p50_snapshot(diag_blk_fd, 0, 1);
    }
#endif

    mkdir("/system_root", 0755);
    int rc_sys = mount("/dev/block/mmcblk0p55", "/system_root", "ext4", MS_RDONLY, "barrier=1");
    klog_msg("<6>init: mount /dev/block/mmcblk0p55 -> /system_root (%s) rc=%d\n", strerror(rc_sys ? errno : 0), rc_sys);
    if (rc_sys != 0) {
        if (enf_fd >= 0) close(enf_fd);
#ifdef DIAG_STAGE0
        if (diag_blk_fd >= 0) { write_p50_snapshot(diag_blk_fd, 901, 1); close(diag_blk_fd); }
#endif
        syscall(SYS_reboot, LINUX_REBOOT_MAGIC1, LINUX_REBOOT_MAGIC2, LINUX_REBOOT_CMD_RESTART2, "");
        return 1;
    }

    int rc_ven = mount("/dev/block/mmcblk0p53", "/system_root/vendor", "ext4", MS_RDONLY, "barrier=1");
    klog_msg("<6>init: mount /dev/block/mmcblk0p53 -> /system_root/vendor (%s) rc=%d\n", strerror(rc_ven ? errno : 0), rc_ven);

    const char *moves[] = {
        "/dev", "/proc", "/sys", "/mnt", "/metadata", "/debug_ramdisk", "/second_stage_resources", NULL
    };
    for (int i = 0; moves[i]; i++) {
        char dst[256];
        snprintf(dst, sizeof(dst), "/system_root%s", moves[i]);
        mkdir(dst, 0755);
        int mrc = mount(moves[i], dst, NULL, MS_MOVE, NULL);
        if (mrc != 0) {
            klog_msg("<3>init: MS_MOVE failed for %s rc=%d\n", moves[i], errno);
        }
    }

    unlink("/init");
    if (chdir("/system_root") != 0 ||
        mount(".", "/", NULL, MS_MOVE, NULL) != 0 ||
        chroot(".") != 0 ||
        chdir("/") != 0) {
        klog_msg("<3>init: SwitchRoot failed%s errno=%d\n", "", errno);
        if (enf_fd >= 0) close(enf_fd);
#ifdef DIAG_STAGE0
        if (diag_blk_fd >= 0) { write_p50_snapshot(diag_blk_fd, 902, 1); close(diag_blk_fd); }
#endif
        syscall(SYS_reboot, LINUX_REBOOT_MAGIC1, LINUX_REBOOT_MAGIC2, LINUX_REBOOT_CMD_RESTART2, "");
        return 1;
    }

    start_enforce_shadow_keeper(enf_fd);

#ifdef DIAG_STAGE0
    start_diag_logger(diag_blk_fd);
#endif

    klog_msg("<6>init: SwitchRoot complete! Executing /system/bin/init selinux_setup%s (%d)\n", "", 0);
    char *next_argv[] = { "/system/bin/init", "selinux_setup", NULL };
    execv("/system/bin/init", next_argv);

    klog_msg("<3>init: execv(/system/bin/init selinux_setup) FAILED%s errno=%d\n", "", errno);
#ifdef DIAG_STAGE0
    int f2 = open("/dev/block/mmcblk0p50", O_RDWR | O_DSYNC | O_CLOEXEC);
    if (f2 >= 0) { write_p50_snapshot(f2, 903, 1); close(f2); }
#endif
    syscall(SYS_reboot, LINUX_REBOOT_MAGIC1, LINUX_REBOOT_MAGIC2, LINUX_REBOOT_CMD_RESTART2, "");
    return 1;
}
