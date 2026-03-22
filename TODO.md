# File Alchemy - Backlog & TODOs

### High Priority

- [ ] **Dynamic Queue Management**: Allow the user to drag-and-drop or select new files to add to the queue _while_ a conversion block is already actively running.
- [ ] **Parallel Processing Thresholds**: Add a threading pool mechanism to allow processing multiple files concurrently, configurable based on the user's CPU core count
- [ ] **Settings & State Persistence**: Create a persistent `settings.json` backend to remember user UI preferences (Theme) and functional preferences.

### Advanced Conversions & Pipelines

- [ ] **Niche 3D Asset Toolkit**: Implement custom pipelines to extract baked textures from `.GLTF` files or batch convert raw mesh topologies (e.g., FBX to OBJ).
- [ ] **Advanced Video Trimming**: Give the user a timeline widget to rapidly split or extract segments from video files without re-encoding them (using `-c copy`).
- [ ] **Audio Extraction**: Explicit one-click UI routes for tearing the audio track (MP3/WAV) off of a given video file.

### UI & Architecture Improvements

- [ ] **Task Canceling System**: Add a "Stop/Cancel" button that securely interrupts the FFmpeg subprocess.
- [ ] **Post-Batch Actions**: Add toggles to "Play sound on completion" or "Open output folder" when a massive queue finally finishes.
- [ ] **Mac/Linux CI Build Matrix**: Expand the `.github/workflows/release.yml` matrix out to produce and upload compiled Darwin (macOS) and Linux targets.
