/** Stable SPA selectors — prefer #id and button names over CSS trees. */

export const ids = {
  productName: '#productName',
  keyFeatures: '#keyFeatures',
  affiliateLink: '#affiliateLink',
  trackAffiliateUrl: '#trackAffiliateUrl',
  trackVideoId: '#trackVideoId',
  socialVideo: '#socialVideo',
  socialSchedule: '#socialSchedule',
  settingsProvider: '#settingsProvider',
  settingsModel: '#settingsModel',
} as const;

export const buttons = {
  generate: 'Generate Videos + YouTube Package',
  cancelJob: 'Cancel Job',
  buildTrackingLink: 'Build Tracking Link',
  settings: 'Settings',
  testLlm: 'Test LLM',
  saveSettings: 'Save Settings',
  postNow: 'Post Now',
  schedulePost: 'Schedule Post',
  dryRun: 'Dry Run',
  publishNow: 'Publish Now',
  loadDashboard: 'Load Dashboard',
} as const;

export const nav = {
  generate: 'Generate',
  analytics: 'Analytics',
  social: 'Social Posting',
} as const;
