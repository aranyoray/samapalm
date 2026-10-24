# SamaHealth onboarding app: field guide

For the two research staff running the visit. One page per thing you do. Nothing here is a medical instruction:
if a participant feels unwell, stop and call the study doctor.

## The short version

* **Names never go in the phone.** The paper consent form carries the name. The phone only ever sees the PID.
  Write the PID on the paper form before you start.
* **Each participant has two records**, which meet on the server by PID:
  * **Enrol** (about 5 minutes): consent, department, age, sex, height, weight, skin tone, known conditions,
    any lab values already on their records, what they had today.
  * **Scan**: the hand, arm circumference and cuff, BP1, the rest, BP2, the palm clip with the Kardia, BP3.
* One of you can enrol while the other sets up the scan. You can use two phones. If you are alone, start the
  scan record for BP1, do the enrol record during the rest, then come back to the scan.

## Setting the phone up once

Settings (top right) -> **Station**: choose *Enrol and history only*, *Scan only*, or *Both on this phone*. This
picks which tab opens first, and only an enrolling phone hands out new PIDs, so two phones cannot give out the
same one. Also set the clip plan (1 x 60 s or 2 x 30 s), the device code and the PID block.

## The four tabs

**Enrol** — the list of enrolments on this phone. *New participant* takes the next PID from this phone's block.
At the end, the review screen shows the stratum chips and whether this participant is a **High**, **Medium** or
**Low** recruitment priority, with the cells they would fill. It is a guide, not a rule: never turn anyone away
on the strength of it.

**Scan** — *New scan* asks which participant. It offers today's enrolments that have no scan yet (from the
server when you are online) and this phone's own enrolments; you can also type a PID. If the PID is not on
either list the app warns you and lets you go on, because the paper form is the record.

**Quality** — every clip this phone has recorded, newest first, with a **Good / Borderline / Retake** grade for
the palm video and for the ECG, and the reason in plain words. Tap one for the detail, to re-analyse it, or to
open the visit. *Check a video* and *Check an ECG file* grade a file recorded outside the app without storing
anything.

**Targets** — how full each recruitment cell is, what is most needed now, and a quick check: tap a sex, a skin
tone band and any conditions to see what that person would count towards. *Refresh* pulls the counts from the
server; it works offline from the last counts it had.

## Recording a clip

1. On the clip screen, press **Record phone clip on this device**. The recorder keeps the screen on and stops
   itself at the clip length, so you do not need to watch the clock.
2. If the recording stops early, the app says so and marks the clip **Fail**. Re-shoot it.
3. As soon as the clip finishes, the app grades the video and, if the Kardia was streaming, the ECG, and
   pre-fills Pass or Fail. **You decide**: change it if you disagree.
4. A grade of *Retake* means the signal is not good enough to analyse. The reason tells you what to fix: too
   dark usually means the torch is off or the palm is not covering the lens; a flat ECG means the fingers are
   not resting on the electrodes.

## The Kardia recording

* If the Kardia was streaming over Bluetooth during the clip, the app has the ECG already.
* Otherwise, take the recording in the Kardia app, then either **Share** it from the Kardia app and pick this
  participant and clip, or use **Import Kardia ECG** on the clip screen.
* Enter what the Kardia app itself showed under *What the Kardia app showed*, and its heart rate. That is the
  device's own result and it is what the participant is told.

## The participant's summary

On the clip screen, **ECG summary for participant** makes a one-page PDF you can print or share: the heart
rate, what the recording showed in plain words, the Kardia app's own result, how clear the recording was, and
that a study doctor reviews every recording. It never names a rhythm, and it is not a medical result.

The **Research pre-read** in the Quality tab is for the study clinician only. Do not show it or read it out to
a participant.

## Uploading

Records upload by themselves when there is a network. The records tab shows what is waiting. If one says
*upload error*, press **Retry upload**. If you see *Signed out by the server*, sign in again: nothing is lost,
the records sit on the phone until you do.

A record the server has already taken cannot have its PID changed. If a PID turns out to be wrong after that,
tell the study coordinator rather than editing around it.

## If something goes wrong

* **The screen locks mid-clip.** It should not: the recorder and the scan screens hold the screen on. If it
  still happens, set the phone's own screen timeout to 10 minutes or more and turn battery optimisation off
  for the app.
* **The Kardia stops sending data.** The app notices a silent stream and reconnects by itself. If the status
  stays on "reconnecting", take the fingers off and put them back, then re-shoot the clip.
* **No PIDs left.** The phone's block is used up: ask the admin for a new block in Settings.
