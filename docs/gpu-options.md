# GPU options for the MVP

Checked 11 October 2026. Recommendation: keep live playback in the browser, and move only separation jobs onto our own GPU worker. Paying for hardware still runs our models and does not use a paid separation API. The product differentiator remains the investigation workflow, evidence, and eventual catalog matching.

| Option | Current published cost | Fits | Tradeoff |
| --- | --- | --- | --- |
| Modal serverless | Starter includes $30/month credits; T4 $0.000164/s (~$0.59/h), L4 $0.000222/s (~$0.80/h), plus CPU/memory/storage | Occasional investor demo and small pilot | Container load time and configured idle timeout are billable; needs remote-job integration; benchmark first |
| Runpod Pod | RTX A5000 listed $0.27/h; RTX 3090 $0.50/h; storage extra | Scheduled demos with a warm worker | Pay while running even without jobs; stop it after each session; actual availability/prices vary |
| Runpod serverless | 16 GB GPU pool listed $0.58/h equivalent; storage extra | On-demand alternative to Modal | Container packaging, cold starts, and job integration |
| Google Colab notebook | Free tier available; limits and GPUs vary | Manual experiments and quality benchmarks | No guaranteed GPU; free notebook is unsuitable as an app-serving backend under Colab restrictions |
| Local CPU + cached results | No hosting expense | Development and rehearsed demos | Slow for new uploads; current 95-second drum pass took about 6m26s on CPU |
| Local Apple GPU (MPS) | Existing hardware, if supported | Possible local acceleration | Current worker pins CPU; installed process did not expose MPS. Validate supported operations and actual speed before enabling |

Sources: [Modal pricing](https://modal.com/pricing), [Runpod pricing](https://www.runpod.io/pricing), [Colab FAQ](https://research.google.com/colaboratory/faq.html).

## Budget examples

GPU compute only: 10 active hours on Modal L4 cost ~$7.99, before CPU/memory/storage and any available credits. Ten running hours on a Runpod A5000 at its listed rate cost $2.70 plus storage. An always-on A5000 at the same rate costs ~$194.40 for 30 days, exceeding our $50 total MVP ceiling. These examples are arithmetic from published rates, not measured per-song costs.

Start with a T4 or L4 candidate, one concurrent job, cached weights, and a small number of benchmark tracks. T4 memory suitability and L4 performance must be measured against our settings. Record load time, inference time, peak memory, total billable seconds, and transfer time. Do not quote per-song processing times until measured.

## Integration path

Browser upload → API/job record → private remote GPU task → validate aligned WAVs → persist results → browser playback. Drum expansion remains a separate task launched only by Separate drums. Pitch/tempo preview remains browser-local; transformed exports remain optional jobs. Use private authenticated calls/storage rather than exposing the current single-user API publicly.

We can keep the UI/API local for the first GPU experiment and later host them separately. Cloud use requires an account and authenticated remote-worker integration; nothing has been deployed or purchased yet. GPU cost estimates do not include full app hosting. MDX23C checkpoint licensing remains unresolved and needs resolution for deployment.

## Downloads

No GPU provider SDK, Docker image, CUDA runtime, or cloud model downloads were installed for this assessment. A cloud image will include Python/PyTorch/CUDA dependencies and model weights; exact image and model transfer sizes must be reported from its pinned dependency plan before installation. The existing MDX checkpoint is 437,652,699 bytes (417.38 MiB). Reuse cached weights rather than downloading for every request.
