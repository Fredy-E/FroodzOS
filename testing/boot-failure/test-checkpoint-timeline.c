/* Regression inputs are synthetic; backend must be an ordinary directory. */
#define KESTREL_TEST
#include "../../builder/diagnostics/kestrel-checkpoint.c"
#include <assert.h>
static void msg(const char *s, uint64_t when) { ingest_kmsg((const unsigned char *)s,strlen(s),when); }
int main(int argc,char **argv) {
    assert(argc==2); fwbase=argv[1]; struct statfs fs; assert(!statfs(fwbase,&fs));
    assert((unsigned long)fs.f_type!=EFIMAGIC); assert(arm_firmware(0));
    memcpy(bootid,"11111111-2222-3333-4444-555555555555",36);
    fw_enabled=1; capture_start=1000;
    msg("6,1,1,-;Linux version synthetic-unit-test\n",1000);
    run_schedule(1000,0); assert(attempted==1);
    msg("6,2,2,-;xhci-hcd xhci-hcd.0.auto: Host supports USB 3.1\n DEVICE=+platform:noise\n",1100);
    run_schedule(1100,0); assert(attempted==1); /* Host root-hub is NOT an external device. */
    msg("3,3,3,-;dwc3-qcom a600000.usb: of_icc_get_by_index: invalid path=-517\n",1200);
    run_schedule(1200,0); assert(attempted==1); /* Regression: do not freeze at first error. */
    msg("4,4,4,-;dwc3-qcom a600000.usb: usb-ddr path unavailable (-517), continuing without it\n",1250);
    msg("4,5,5,-;dwc3-qcom a600000.usb: apps-usb path unavailable (-517), continuing without it\n",1300);
    run_schedule(2400,0); assert(attempted==3);
    for(unsigned i=0;i<2000;i++) msg("7,6,6,-;qcom-rpmhpd power-controller: sync_state() pending due to irrelevant.device\n",3000);
    run_schedule(13000,0); assert(attempted==7);
    run_schedule(56000,0); assert(attempted==15); /* Later checkpoint even on a silent kernel. */
    for(unsigned i=0;i<100;i++) run_schedule(57000+i,0);
    assert(attempted==15); assert(!arm_firmware(0));
    char path[512]; var_path(path,sizeof(path),1); FILE *f=fopen(path,"rb"); assert(f);
    unsigned char b[RECORD+5]={0}; size_t n=fread(b,1,sizeof(b)-1,f); fclose(f); assert(n<=RECORD+4);
    assert(strstr((char *)b+4+HEADER,"usb-ddr path unavailable"));
    assert(strstr((char *)b+4+HEADER,"apps-usb path unavailable"));
    assert(!strstr((char *)b+4+HEADER,"DEVICE=+platform:noise"));
    assert(!strstr((char *)b+4+HEADER,"sync_state() pending"));
    puts("TIMELINE_PASS: delayed-error + followups + silent-late + four-write-budget + no-debug-noise");
    return 0;
}
