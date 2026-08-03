import type { Page, Route } from '@playwright/test';

export const MOCK_JOB_ID = 'e2e-mock-job-1';

const readinessOk = {
  ready: true,
  blockers: [] as string[],
  warnings: [] as string[],
  checks: {
    ffmpeg: true,
    ffprobe: true,
    llm: true,
    llm_provider: 'ollama',
    llm_model: 'mock-model',
    tts_best: 'gtts',
    tts_quality: false,
    tts_providers: { gtts: true },
  },
  default_video_preset: 'balanced',
};

const mockResults = {
  id: MOCK_JOB_ID,
  mode: 'single',
  status: 'complete',
  progress: 100,
  current_step: 'Done',
  errors: [] as string[],
  warnings: [] as string[],
  script_errors: [] as string[],
  video_warnings: [] as string[],
  other_errors: [] as string[],
  summary: {
    videos_ready: 1,
    videos_expected: 1,
    packages_ready: 1,
    packages_expected: 1,
    is_partial: false,
  },
  product_info: {
    product_name: 'E2E Test Widget',
    affiliate_link: 'https://amzn.to/e2e-test',
  },
  hook_types: ['curiosity'],
  formats: ['short_form'],
  results: {
    curiosity: {
      scripts: { short_form: 'Hook script body for e2e.' },
      videos: { short_form: { path: `${MOCK_JOB_ID}/curiosity_short.mp4`, exists: true } },
      youtube_assets: {
        short_form: {
          seo_title: 'E2E Widget Review',
          seo_description: 'Test description',
          hashtags: ['#e2e'],
          pinned_comment: 'Link in description',
        },
      },
    },
  },
  trust_inputs: {},
  audit: null,
};

async function fulfillJson(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });
}

/**
 * Install Tier-1 network stubs for heavy / flaky APIs.
 * Catalog GETs (hooks, providers, bg-recommend) pass through to the real server.
 */
export async function installMockedApiRoutes(page: Page) {
  let statusPolls = 0;
  let cancelHit = false;
  let holdRunning = false;

  await page.route('**/api/readiness', (route) => fulfillJson(route, readinessOk));

  await page.route('**/api/generate', async (route) => {
    if (route.request().method() !== 'POST') {
      await route.continue();
      return;
    }
    statusPolls = 0;
    cancelHit = false;
    await fulfillJson(route, {
      job_id: MOCK_JOB_ID,
      status: 'running',
      mode: 'single',
    });
  });

  await page.route('**/api/batch-generate', async (route) => {
    if (route.request().method() !== 'POST') {
      await route.continue();
      return;
    }
    await fulfillJson(route, {
      job_id: MOCK_JOB_ID,
      status: 'running',
      mode: 'batch',
      product_count: 2,
    });
  });

  await page.route('**/api/status/**', async (route) => {
    if (cancelHit) {
      await fulfillJson(route, {
        id: MOCK_JOB_ID,
        status: 'cancelled',
        progress: 40,
        current_step: 'Cancelled by user',
        errors: ['Job cancelled'],
        warnings: [],
        script_errors: [],
        video_warnings: [],
        other_errors: ['Job cancelled'],
      });
      return;
    }
    if (holdRunning) {
      await fulfillJson(route, {
        id: MOCK_JOB_ID,
        status: 'running',
        progress: 20,
        current_step: 'Writing script...',
        errors: [],
        warnings: [],
        script_errors: [],
        video_warnings: [],
        other_errors: [],
      });
      return;
    }
    statusPolls += 1;
    if (statusPolls < 2) {
      await fulfillJson(route, {
        id: MOCK_JOB_ID,
        status: 'running',
        progress: 35,
        current_step: 'Rendering video...',
        errors: [],
        warnings: [],
        script_errors: [],
        video_warnings: [],
        other_errors: [],
      });
      return;
    }
    await fulfillJson(route, {
      id: MOCK_JOB_ID,
      status: 'complete',
      progress: 100,
      current_step: 'Done',
      errors: [],
      warnings: [],
      script_errors: [],
      video_warnings: [],
      other_errors: [],
      audit: null,
    });
  });

  await page.route('**/api/cancel/**', async (route) => {
    if (route.request().method() !== 'POST') {
      await route.continue();
      return;
    }
    cancelHit = true;
    await fulfillJson(route, {
      job_id: MOCK_JOB_ID,
      status: 'cancelling',
      message: 'Cancel requested',
    });
  });

  await page.route('**/api/results/**', (route) => fulfillJson(route, mockResults));

  await page.route('**/api/publish/batch', async (route) => {
    if (route.request().method() !== 'POST') {
      await route.continue();
      return;
    }
    const body = route.request().postDataJSON() as { dry_run?: boolean };
    await fulfillJson(route, {
      status: 'ok',
      dry_run: !!body?.dry_run,
      results: [{ platform: 'youtube', status: 'success', dry_run: !!body?.dry_run }],
    });
  });

  await page.route('**/api/social/post', async (route) => {
    if (route.request().method() !== 'POST') {
      await route.continue();
      return;
    }
    const body = route.request().postDataJSON() as { dry_run?: boolean };
    await fulfillJson(route, {
      status: 'success',
      dry_run: !!body?.dry_run,
      post_id: 'mock-post',
    });
  });

  await page.route('**/api/social/schedule', async (route) => {
    if (route.request().method() !== 'POST') {
      await route.continue();
      return;
    }
    await fulfillJson(route, { status: 'scheduled', id: 'mock-sched-1' });
  });

  await page.route('**/api/jobs/postable', (route) =>
    fulfillJson(route, {
      jobs: [
        {
          job_id: MOCK_JOB_ID,
          status: 'complete',
          mode: 'single',
          product_name: 'E2E Test Widget',
          content_style: 'honest_review',
          batch_products: [],
          variants: [
            {
              hook_type: 'curiosity',
              video_format: 'short_form',
              video_file: 'curiosity_short.mp4',
              path_prefix: '',
              thumbnail_file: null,
              product_slug: null,
              label: 'E2E Test Widget — honest review — Short',
              caption_hint: 'E2E caption',
              hashtags: ['#e2e'],
              seo_title: 'E2E Widget',
            },
          ],
        },
      ],
    }),
  );

  await page.route('**/api/social/status', (route) =>
    fulfillJson(route, {
      youtube: 'Not Configured',
      instagram: 'Not Configured',
      facebook: 'Not Configured',
      tiktok: 'Not Configured',
      rumble: 'Not Configured',
    }),
  );

  await page.route('**/api/social/queue', (route) => fulfillJson(route, { queue: [] }));

  await page.route('**/api/oauth/status', (route) =>
    fulfillJson(route, {
      youtube: { connected: true, details: { channel_id: 'UC_e2e' } },
      instagram: { connected: false, details: {} },
      facebook: { connected: false, details: {} },
      tiktok: { connected: false, details: {} },
      rumble: { connected: false, details: {} },
    }),
  );

  await page.route('**/api/oauth/config', (route) =>
    fulfillJson(route, {
      youtube: true,
      meta: false,
      tiktok: false,
    }),
  );

  await page.route('**/api/oauth/youtube/authorize', (route) =>
    fulfillJson(route, {
      authorize_url: 'https://accounts.google.com/o/oauth2/v2/auth?client_id=e2e-mock&state=e2e',
      state: 'e2e',
    }),
  );

  await page.route('**/api/llm/test**', (route) =>
    fulfillJson(route, { ok: true, detail: 'mock ok', sample: 'hello' }),
  );

  await page.route('**/api/llm/models**', (route) =>
    fulfillJson(route, { models: ['mock-model-a', 'mock-model-b'], source: 'mock' }),
  );

  await page.route('**/api/config', async (route) => {
    if (route.request().method() !== 'POST') {
      await route.continue();
      return;
    }
    await fulfillJson(route, {
      status: 'ok',
      provider: 'ollama',
      base_url: 'http://localhost:11434/v1',
      model: 'mock-model',
      has_api_key: false,
    });
  });

  // Expose cancel flag for assertions via page evaluation helper storage
  await page.addInitScript(() => {
    (window as unknown as { __e2eCancelStub?: boolean }).__e2eCancelStub = false;
  });

  return {
    wasCancelled: () => cancelHit,
    holdRunning: (value = true) => {
      holdRunning = value;
    },
    resetStatusPolls: () => {
      statusPolls = 0;
      cancelHit = false;
      holdRunning = false;
    },
  };
}
