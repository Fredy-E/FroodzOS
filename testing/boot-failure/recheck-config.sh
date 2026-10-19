#!/bin/bash
# Re-verify the =m claims (a wrong config read would invalidate them).
KSRC=/home/builder/src/ksrc
grep -E '^CONFIG_(DRM_MSM|VIDEO_QCOM_VENUS|VIDEO_QCOM_CAMSS|ATH12K|SCSI_UFS_QCOM|QCOM_Q6V5_PAS|SCSI_UFSHCD_PLATFORM)=' "$KSRC/.config"
echo ---; ls -la "$KSRC/.config"; date
