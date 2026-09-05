import type { RecoveryAction } from "./types";

export const actionLabels: Record<RecoveryAction, string> = {
  WAIT_FOR_RETRY: "Wait for Razorpay retry",
  REQUEST_PAYMENT_METHOD_UPDATE: "Request payment update",
  CREATE_RECOVERY_LINK: "Create recovery link",
  ESCALATE_HUMAN: "Escalate to human",
  STOP_CONTACT: "Stop contact",
};

export const money = (paise: number) =>
  new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(paise / 100);

export const moneyRupees = (rupees: number) =>
  new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(rupees);

export const cleanLabel = (value: string) => value.replaceAll("_", " ").replace(/\b\w/g, (m) => m.toUpperCase());
