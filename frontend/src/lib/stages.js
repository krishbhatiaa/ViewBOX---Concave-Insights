export const STAGE_TONE = {
  Approved: "emerald",
  Completed: "emerald",
  Paid: "emerald",
  Rejected: "rose",
  Failed: "rose",
  Waitlisted: "amber",
  Fit: "amber",
  Pending: "amber",
  Lead: "sky",
  ApprovedPay: "sky",
};

export function toneForStage(stage) {
  if (stage === "Approved") return "emerald";
  return STAGE_TONE[stage] || "slate";
}

export const STAGE_EXPLANATION = {
  Lead: "You have signed up. Our team is checking your profile against survey criteria.",
  Fit: "Your profile matches. You are in the pool for upcoming surveys.",
  Completed: "You completed a survey. Thank you!",
  Failed: "Your profile was not selected this time.",
};

export const PAYOUT_LABEL = {
  Pending: "Pending ops approval",
  Approved: "Approved, payment on the way",
  Paid: "Paid",
};

export const INCOME_OPTIONS = ["<5L", "5-10L", "10L+"];
export const GENDER_OPTIONS = ["Male", "Female", "Other"];
