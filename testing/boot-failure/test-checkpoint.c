/* Test backend is a newly created ordinary directory, NEVER efivarfs. */
#define KESTREL_TEST
#include "../../builder/diagnostics/kestrel-checkpoint.c"
#include <assert.h>
int main(int argc,char **argv) {
    assert(argc==2); fwbase=argv[1]; struct statfs fs; assert(statfs(fwbase,&fs)==0);
    assert((unsigned long)fs.f_type!=EFIMAGIC);
    memcpy(bootid,"11111111-2222-3333-4444-555555555555",36);
    assert(crc32_bytes((unsigned char *)"123456789",9)==0xcbf43926U);
    assert(arm_firmware(1)==0); /* Wrong filesystem is rejected. */
    assert(arm_firmware(0)==1);
    append_ring((unsigned char *)"synthetic checkpoint test\n",26);
    fw_enabled=0; assert(checkpoint(0,"off")==0); assert(attempted==0);
    fw_enabled=1;
    for(unsigned i=0;i<SLOTS;i++) assert(checkpoint(i,"test")==1);
    assert(attempted==15);
    for(unsigned i=0;i<20;i++) assert(checkpoint(i%SLOTS,"duplicate")==0);
    assert(checkpoint(4,"invalid")==0);
    assert(arm_firmware(0)==0); /* A new boot preserves old evidence. */
    unsigned char big[RING+5]; memset(big,'a',sizeof(big)); append_ring(big,sizeof(big));
    assert(ringlen==RING);
    unsigned char rec[RECORD]; size_t made=make_record(rec,3,"bounded"); assert(made<=RECORD && made>HEADER);
    char oldbase[512]; snprintf(oldbase,sizeof(oldbase),"%s",fwbase);
    fwbase="/nonexistent-kestrel-unit-test-directory"; attempted=0; fw_enabled=1;
    assert(checkpoint(0,"failure")==-1); assert(fw_enabled==0 && attempted==1);
    assert(checkpoint(1,"no-retry")==0 && attempted==1);
    fwbase=oldbase;
    puts("CHECKPOINT_UNIT_PASS: crc, off, fs-gate, write-budget, duplicates, existing-records, bounds, error-stop");
    return 0;
}
