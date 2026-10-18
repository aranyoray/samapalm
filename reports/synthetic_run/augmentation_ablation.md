# Training ablation (with versus without augmented copies)

small-sample ablation; differences at this n are not distinguishable from noise.

| task | arm | metric | n |
|---|---|---|---|
| pulse_rate | without_augmentation | MAE 4.61 bpm | 12 |
| pulse_rate | with_augmentation | MAE 7.16 bpm | 12 |
| bp_tertile | without_augmentation | accuracy 0.33 (chance 0.33) | 12 |
| bp_tertile | with_augmentation | accuracy 0.33 (chance 0.33) | 12 |
