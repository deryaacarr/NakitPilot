import { apiRequest } from "@/lib/api/client";

export type OnboardingStep = { key: string; label: string };

export type OnboardingState = {
  current_step: string;
  completed_steps: string[];
  wizard_completed: boolean;
  sample_data_enabled: boolean;
  steps: OnboardingStep[];
  progress: {
    score: number;
    max_score: number;
    items: Array<{ key: string; label: string; weight: number; done: boolean }>;
  };
};

export type Guidance = {
  empty_states: Array<{
    surface: string;
    title: string;
    action_label: string;
    action_href: string;
    secondary_label?: string;
    secondary_action?: string;
  }>;
  tooltips: Array<{ key: string; target: string; text: string; show: boolean }>;
  checklist: Array<{ key: string; label: string; weight: number; done: boolean }>;
  score: number;
  sample_report: {
    title: string;
    metrics: Array<{ label: string; value: string }>;
    note: string;
  };
  help_links: Array<{ label: string; href: string }>;
  announcements: Array<{ key: string; title: string; body: string; help_url: string }>;
  wizard_completed: boolean;
  sample_data_enabled: boolean;
};

export function fetchOnboarding() {
  return apiRequest<OnboardingState>("/api/onboarding/");
}

export function updateOnboarding(body: {
  current_step?: string;
  completed_steps?: string[];
  wizard_completed?: boolean;
}) {
  return apiRequest<OnboardingState>("/api/onboarding/", {
    method: "PATCH",
    body,
  });
}

export function fetchOnboardingProgress() {
  return apiRequest<OnboardingState["progress"]>("/api/onboarding/progress/");
}

export function enableSampleData() {
  return apiRequest<Record<string, unknown>>("/api/onboarding/sample-data/", {
    method: "POST",
    body: {},
  });
}

export function disableSampleData() {
  return apiRequest<Record<string, unknown>>("/api/onboarding/sample-data/", {
    method: "DELETE",
  });
}

export function fetchGuidance() {
  return apiRequest<Guidance>("/api/onboarding/guidance/");
}

export function trackProductEvent(event_name: string, properties: Record<string, unknown> = {}) {
  return apiRequest<{ id: number }>("/api/onboarding/events/", {
    method: "POST",
    body: { event_name, properties },
  });
}
