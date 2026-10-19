/* SPDX-License-Identifier: MIT
 * Bounded RAM capture + optional write-once EFI checkpoints.
 * Never updates/deletes a firmware variable; existing evidence disarms it.
 * Firmware runtime calls may still hang on broken firmware: explicit opt-in.
 */
#define _GNU_SOURCE
#include <errno.h>
#include <dirent.h>
#include <stdarg.h>
#include <sys/utsname.h>
#include <fcntl.h>
#include <poll.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/vfs.h>
#include <time.h>
#include <unistd.h>

#define GUID "674b8af1-da8e-4c2b-a84c-467e2d36c97c"
#define EFIBASE "/sys/firmware/efi/efivars"
#define RAMBASE "/run/kestrel-capture"
#define EFIMAGIC 0xde5e81e4UL
#define HEADER 80U
#define RECORD 1024U
#define RING 65536U
#define SLOTS 4U
#define DEADLINE 60U
static volatile sig_atomic_t stopped;
static unsigned char ringbuf[RING];
static size_t ringlen;
static unsigned int attempted;
static int fw_enabled;
static const char *fwbase = EFIBASE;
static char bootid[37];
/* Firmware retains selected evidence, not verbose kmsg metadata/debug noise. */
static char selected[4096];
static size_t selected_len;
static uint64_t capture_start, error_due;
static int input_error;


static void stop_handler(int sig) { (void)sig; stopped = 1; }
static void console_msg(const char *s) {
    /* One-line banner for screen photos; failures are silent by design. */
    FILE *c=fopen("/dev/console","w");
    if(c) { fputs(s,c); fputc('\n',c); fclose(c); }
}
static uint64_t now_ms(void) {
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC, &t)) return 0;
    return (uint64_t)t.tv_sec * 1000U + (unsigned)t.tv_nsec / 1000000U;
}
static void le32(unsigned char *p, uint32_t x) {
    for (unsigned i=0; i<4; i++) p[i]=(unsigned char)(x>>(i*8));
}
static uint32_t crc32_bytes(const unsigned char *p, size_t n) {
    uint32_t c=~0U;
    while(n--) { c^=*p++; for(unsigned i=0;i<8;i++) c=(c>>1)^(0xedb88320U & (0U-(c&1))); }
    return ~c;
}
static void append_ring(const unsigned char *p, size_t n) {
    if(n>=RING) { p+=n-RING; n=RING; ringlen=0; }
    if(ringlen+n>RING) { size_t drop=ringlen+n-RING; memmove(ringbuf,ringbuf+drop,ringlen-drop); ringlen-=drop; }
    memcpy(ringbuf+ringlen,p,n); ringlen+=n;
}
static void add_text(char *out, size_t cap, const char *fmt, ...) {
    size_t used=strlen(out);
    if(used>=cap-1) return;
    va_list ap; va_start(ap,fmt); vsnprintf(out+used,cap-used,fmt,ap); va_end(ap);
}
static int read_text(const char *path, char *out, size_t cap) {
    int fd=open(path,O_RDONLY|O_NONBLOCK|O_CLOEXEC|O_NOFOLLOW);
    if(fd<0) return 0;
    ssize_t n=read(fd,out,cap-1); close(fd);
    if(n<=0) return 0;
    out[n]=0;
    out[strcspn(out,"\r\n")]=0;
    return 1;
}
static void state_summary(char *out, size_t cap) {
    struct utsname u;
    out[0]=0;
    if(!uname(&u)) add_text(out,cap,"capture=v2 kernel=%.32s %.64s\n",u.release,u.version);
    unsigned roots=0, external=0; DIR *d=opendir("/sys/bus/usb/devices");
    if(d) {
        struct dirent *e; unsigned scanned=0;
        while((e=readdir(d)) && scanned++<256) {
            if(e->d_name[0]=='.' || strchr(e->d_name,':')) continue;
            char path[512], vid[32];
            snprintf(path,sizeof(path),"/sys/bus/usb/devices/%s/idVendor",e->d_name);
            if(!read_text(path,vid,sizeof(vid))) continue;
            if(!strncmp(e->d_name,"usb",3)) roots++; else external++;
        }
        closedir(d);
    }
    struct stat st;
    int label=stat("/dev/disk/by-label/KESTREL_A64",&st)==0 && S_ISBLK(st.st_mode);
    add_text(out,cap,"usb_roots=%u external_usb=%u label=%s input_errno=%d\n",
             roots,external,label?"present":"missing",input_error);
    const char *ports[]={"a200000.usb","a400000.usb","a600000.usb","a800000.usb"};
    for(unsigned i=0;i<4;i++) {
        char path[128], target[256];
        snprintf(path,sizeof(path),"/sys/bus/platform/devices/%s/driver",ports[i]);
        ssize_t n=readlink(path,target,sizeof(target)-1);
        if(n>=0) { target[n]=0; add_text(out,cap,"%s=bound ",ports[i]); }
        else add_text(out,cap,"%s=unbound ",ports[i]);
    }
    add_text(out,cap,"\n");
    /* init's mount failure is userspace text, not /dev/kmsg. With rd.log=file,
     * tee records it here even when no USB or keyboard exists. */
    int fd=open("/run/initramfs/init.log",O_RDONLY|O_NONBLOCK|O_CLOEXEC);
    if(fd>=0) {
        char tail[16385]; off_t end=lseek(fd,0,SEEK_END);
        if(end>16384) lseek(fd,end-16384,SEEK_SET); else lseek(fd,0,SEEK_SET);
        ssize_t n=read(fd,tail,sizeof(tail)-1); close(fd);
        if(n>0) {
            tail[n]=0;
            if(strstr(tail,"device did not show up") || strstr(tail,"Falling back to interactive prompt"))
                add_text(out,cap,"initramfs_boot_device_timeout=seen\n");
        }
    }
}
static void ingest_kmsg(const unsigned char *buf, size_t n, uint64_t when) {
    append_ring(buf,n);
    /* /dev/kmsg yields one record, including optional SUBSYSTEM/DEVICE lines.
     * Keep only the first message line, with its timestamp for chronology. */
    const char *p=memchr(buf,';',n);
    if(!p) return;
    size_t offset=(size_t)(++p-(const char *)buf), len=n-offset;
    const char *end=memchr(p,'\n',len); if(end) len=(size_t)(end-p);
    char line[512]; if(len>=sizeof(line)) len=sizeof(line)-1;
    memcpy(line,p,len); line[len]=0;
    if(strstr(line,"sync_state() pending") || strstr(line,"calling ") || strstr(line,"initcall ")) return;
    int error=strstr(line,"invalid path") || strstr(line,"continuing without it") ||
              strstr(line,"remove, state") || strstr(line,"Kernel panic");
    int useful=error || strstr(line,"dwc3") || strstr(line,"xhci") || strstr(line,"usb ") ||
               strstr(line,"-phy") || strstr(line,"pmic-glink") || strstr(line,"Linux version");
    if(!useful) return;
    if(error && !error_due) error_due=when+1200U;
    char item[544]; int k=snprintf(item,sizeof(item),"%llu %s\n",(unsigned long long)when,line);
    size_t take=(size_t)k; if(take>=sizeof(item)) take=sizeof(item)-1;
    if(selected_len+take>=sizeof(selected)) {
        size_t drop=selected_len+take-(sizeof(selected)-1);
        memmove(selected,selected+drop,selected_len-drop); selected_len-=drop;
    }
    memcpy(selected+selected_len,item,take); selected_len+=take; selected[selected_len]=0;
}
static size_t make_record(unsigned char *out, unsigned slot, const char *reason) {
    char payload[RECORD-HEADER+1]; state_summary(payload,360);
    size_t used=strlen(payload), room=sizeof(payload)-1-used;
    size_t take=selected_len<room ? selected_len : room;
    size_t from=selected_len-take;
    /* Start on a complete message when a bounded tail has dropped a prefix. */
    if(from && selected[from-1]!='\n') {
        const char *nl=memchr(selected+from,'\n',take);
        if(nl) { size_t skip=(size_t)(nl-(selected+from))+1; from+=skip; take-=skip; }
    }
    memcpy(payload+used,selected+from,take); size_t len=used+take;
    memset(out,0,RECORD); memcpy(out,"KSTRLOG1",8);
    le32(out+8,1); le32(out+12,slot); le32(out+16,(uint32_t)len);
    uint64_t ms=now_ms(); for(unsigned i=0;i<8;i++) out[24+i]=(unsigned char)(ms>>(8*i));
    memcpy(out+32,bootid,36); snprintf((char *)out+68,12,"%s",reason);
    memcpy(out+HEADER,payload,len);
    le32(out+20,crc32_bytes(out,HEADER+len)); return HEADER+len;
}
static void var_path(char *out, size_t n, unsigned slot) {
    snprintf(out,n,"%s/KestrelBoot%02u-%s",fwbase,slot,GUID);
}
static int arm_firmware(int check_mount) {
    struct statfs fs;
    if(check_mount && (statfs(fwbase,&fs) || (unsigned long)fs.f_type!=EFIMAGIC ||
       (uint64_t)fs.f_bavail*(uint64_t)fs.f_bsize < 32768U+SLOTS*(RECORD+4U))) {
        fprintf(stderr,"KESTREL_FW_REFUSED: efivarfs unavailable or reserve too small\n"); return 0;
    }
    for(unsigned i=0;i<SLOTS;i++) {
        char path[512]; struct stat st; var_path(path,sizeof(path),i);
        if(lstat(path,&st)==0 || errno!=ENOENT) {
            fprintf(stderr,"KESTREL_FW_REFUSED: previous evidence or inaccessible slot\n"); return 0;
        }
    }
    return 1;
}
static int checkpoint(unsigned slot, const char *reason) {
    if(!fw_enabled || slot>=SLOTS || (attempted & (1U<<slot))) return 0;
    attempted|=1U<<slot; /* One attempt, even on failure; no firmware retries. */
    unsigned char data[RECORD+4], verify[RECORD+4];
    le32(data,7); size_t len=4+make_record(data+4,slot,reason);
    char path[512]; var_path(path,sizeof(path),slot);
    int fd=open(path,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC,0600);
    if(fd<0) goto fail;
    ssize_t n=write(fd,data,len); int saved=errno; int closed=close(fd); errno=saved;
    if(n!=(ssize_t)len || closed) goto fail;
    fd=open(path,O_RDONLY|O_NOFOLLOW|O_CLOEXEC);
    if(fd<0) goto fail;
    n=read(fd,verify,sizeof(verify)); closed=close(fd);
    if(n!=(ssize_t)len || closed || memcmp(data,verify,len)) { errno=EIO; goto fail; }
    fprintf(stderr,"KESTREL_FW_SAVED slot=%u bytes=%zu reason=%s\n",slot,len,reason);
    char banner[128]; snprintf(banner,sizeof(banner),"KESTREL_FW_SAVED slot=%u reason=%s",slot,reason);
    console_msg(banner);
    return 1;
fail:
    fprintf(stderr,"KESTREL_FW_STOP: slot=%u errno=%d (%s)\n",slot,errno,strerror(errno));
    console_msg("KESTREL_FW_STOP: write/readback failed; see RAM status if accessible");
    fw_enabled=0; return -1;
}
static void run_schedule(uint64_t now, int finish) {
    uint64_t elapsed=now-capture_start;
    checkpoint(0,"earlyhook");
    if(finish || (error_due && now>=error_due) || elapsed>=6000U)
        checkpoint(1,error_due ? "post-error" : "usb-state");
    if(finish || elapsed>=12000U) checkpoint(2,"late-usb");
    /* Preserve a later observation after the live-root device timeout, even
     * with no further kmsg messages. Never repeatedly update a variable. */
    if(finish || elapsed>=55000U) checkpoint(3,finish ? "stop" : "timeout");
}
#ifndef KESTREL_TEST
static void save_ram(void) {
    char path[]=RAMBASE "/early-kmsg.tmp";
    int fd=open(path,O_WRONLY|O_CREAT|O_TRUNC|O_NOFOLLOW|O_CLOEXEC,0600);
    if(fd<0) return;
    size_t off=0;
    while(off<ringlen) { ssize_t n=write(fd,ringbuf+off,ringlen-off); if(n<=0) break; off+=(size_t)n; }
    int closed=close(fd);
    if(off==ringlen && !closed) rename(path,RAMBASE "/early-kmsg.log");
}
static int has_arg(const char *cmdline, const char *arg) {
    size_t len=strlen(arg);
    for(const char *p=cmdline; *p;) {
        while(*p==' ' || *p=='\n') p++;
        const char *end=p; while(*end && *end!=' ' && *end!='\n') end++;
        if((size_t)(end-p)==len && !memcmp(p,arg,len)) return 1;
        p=end;
    }
    return 0;
}
int main(void) {
    char cmdline[8192]={0}; FILE *f=fopen("/proc/cmdline","r");
    if(!f) return 0;
    if(!fgets(cmdline,sizeof(cmdline),f)) { fclose(f); return 0; } fclose(f);
    if(!has_arg(cmdline,"kestrel_log=1") && !has_arg(cmdline,"kestrel_efilog=1")) return 0;
    if(mkdir(RAMBASE,0700) && errno!=EEXIST) return 0;
    f=fopen("/proc/sys/kernel/random/boot_id","r");
    if(!f) return 0;
    if(!fgets(bootid,sizeof(bootid),f)) { fclose(f); return 0; } fclose(f);
    if(strlen(bootid)!=36) return 0;
    fw_enabled=has_arg(cmdline,"kestrel_efilog=1") && arm_firmware(1);
    if(has_arg(cmdline,"kestrel_efilog=1") && !fw_enabled)
        console_msg("KESTREL_FW_DISARMED: existing records or efivarfs not writable; no new firmware capture");
    struct sigaction sa={0}; sa.sa_handler=stop_handler; sigemptyset(&sa.sa_mask);
    sigaction(SIGTERM,&sa,NULL); sigaction(SIGINT,&sa,NULL);
    int input=open("/dev/kmsg",O_RDONLY|O_NONBLOCK|O_CLOEXEC);
    if(input<0) { input_error=errno; perror("KESTREL_RAM_CAPTURE"); }
    fprintf(stderr,"KESTREL_RAM_CAPTURE_ACTIVE firmware=%d max_writes=4 deadline=60s capture=v2\n",fw_enabled);
    console_msg("KESTREL_RAM_CAPTURE_ACTIVE v2: max 4 firmware writes; wait for SAVED slot=3");
    capture_start=now_ms(); uint64_t saved=capture_start;
    run_schedule(capture_start,0);
    while(!stopped && now_ms()-capture_start<DEADLINE*1000U && access(RAMBASE "/stop-early",F_OK)) {
        unsigned char buf[16385]; ssize_t n=input>=0 ? read(input,buf,sizeof(buf)-1) : -1;
        if(n>0) {
            ingest_kmsg(buf,(size_t)n,now_ms());
        } else {
            if(input>=0 && (n==0 || (errno!=EAGAIN && errno!=EPIPE && errno!=EINTR))) {
                input_error=n==0 ? EIO : errno;
                fprintf(stderr,"KESTREL_KMSG_STOP errno=%d; timed state capture continues\n",input_error);
                close(input); input=-1;
            }
            struct pollfd pfd={.fd=input,.events=POLLIN}; poll(&pfd,1,100);
        }
        run_schedule(now_ms(),0);
        if(now_ms()-saved>=250U) { save_ram(); saved=now_ms(); }
    }
    save_ram(); run_schedule(now_ms(),1); if(input>=0) close(input);
    fprintf(stderr,"KESTREL_RAM_CAPTURE_STOPPED attempts=0x%x\n",attempted);
    console_msg("KESTREL_RAM_CAPTURE_STOPPED v2"); return 0;
}
#endif
