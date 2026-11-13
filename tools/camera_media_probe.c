/* Read-only media-controller ABI probe. Run under the camera UID/group.
 * Builds with Linux arm64/arm cross GCC -static. No sensor ioctls are issued.
 */
#include <errno.h>
#include <fcntl.h>
#include <linux/media.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>

int main(int argc, char **argv)
{
    const char *log = sizeof(void *) == 8
        ? "/data/local/tmp/codex-camera/probe64.txt"
        : "/data/local/tmp/codex-camera/probe32.txt";
    if (!freopen(log, "w", stdout)) return 2;
    setvbuf(stdout, NULL, _IONBF, 0);
    printf("pointer=%zu entity_size=%zu info_size=%zu enum_ioctl=%#lx\n",
           sizeof(void *), sizeof(struct media_entity_desc),
           sizeof(struct media_device_info), (unsigned long)MEDIA_IOC_ENUM_ENTITIES);
    for (int index = 0; index < 8; ++index) {
        char path[32];
        snprintf(path, sizeof(path), "/dev/media%d", index);
        int fd = open(path, O_RDWR | O_NONBLOCK);
        if (fd < 0) {
            printf("%s open errno=%d\n", path, errno);
            continue;
        }
        struct media_device_info info = {0};
        int rc = ioctl(fd, MEDIA_IOC_DEVICE_INFO, &info);
        printf("%s info rc=%d errno=%d driver=%.16s model=%.32s\n",
               path, rc, rc < 0 ? errno : 0, info.driver, info.model);
        unsigned int next = MEDIA_ENT_ID_FLAG_NEXT;
        for (int count = 0; count < 256; ++count) {
            struct media_entity_desc ent;
            memset(&ent, 0, sizeof(ent));
            ent.id = next;
            rc = ioctl(fd, MEDIA_IOC_ENUM_ENTITIES, &ent);
            printf("request=%#x rc=%d errno=%d id=%#x name=%.32s type=%#x group=%u dev=%u:%u\n",
                   next, rc, rc < 0 ? errno : 0, ent.id, ent.name, ent.type,
                   ent.group_id, ent.dev.major, ent.dev.minor);
            if (rc < 0 || (ent.id | MEDIA_ENT_ID_FLAG_NEXT) == next) break;
            next = ent.id | MEDIA_ENT_ID_FLAG_NEXT;
        }
        close(fd);
    }
    if (sizeof(void *) == 8 && argc == 2) {
        fflush(stdout);
        execl(argv[1], argv[1], (char *)NULL);
        return 3;
    }
    return 0;
}
