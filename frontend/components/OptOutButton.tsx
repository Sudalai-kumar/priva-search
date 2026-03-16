"use client";

import type { OptOutInfo } from "@/lib/types";

interface OptOutButtonProps {
  brandName: string;
  optOutInfo: OptOutInfo;
}

/**
 * "Take Action" opt-out CTA.
 *
 * - If do_not_sell_url or deletion_request_url exists → render a direct link
 * - If neither exists but privacy_contact_email is set → open a pre-filled mailto:
 * - Never claims the opt-out is guaranteed — framed as "sending a request"
 */
export default function OptOutButton({ brandName, optOutInfo }: OptOutButtonProps) {
  const { do_not_sell_url, deletion_request_url, privacy_contact_email } = optOutInfo;

  const directUrl = do_not_sell_url ?? deletion_request_url;

  if (directUrl) {
    return (
      <a
        id="optout-direct-link"
        href={directUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white
                   font-semibold text-sm px-5 py-3 rounded-xl transition-colors duration-150"
      >
        <span>🔒</span>
        Take Action — Submit Opt-Out Request
        <svg className="w-4 h-4 opacity-70" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
        </svg>
      </a>
    );
  }

  if (privacy_contact_email) {
    const subject = encodeURIComponent(`Data Deletion / Opt-Out Request`);
    const body = encodeURIComponent(
      `Hello ${brandName} Privacy Team,\n\n` +
        `I am writing to formally request that you delete all personal data you hold about me ` +
        `and opt me out of any data selling or sharing.\n\n` +
        `Please confirm receipt and provide a timeline for completing this request.\n\n` +
        `Thank you.`
    );
    const mailtoUrl = `mailto:${privacy_contact_email}?subject=${subject}&body=${body}`;

    return (
      <div className="flex flex-col gap-2">
        <a
          id="optout-mailto-link"
          href={mailtoUrl}
          className="inline-flex items-center gap-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-200
                     font-semibold text-sm px-5 py-3 rounded-xl transition-colors duration-150"
        >
          <span>✉️</span>
          Send Opt-Out Email Request
        </a>
        <p className="text-xs text-zinc-500">
          This opens a pre-filled email. Sending it is a request — fulfilment is not guaranteed.
        </p>
      </div>
    );
  }

  return (
    <p className="text-sm text-zinc-500 italic">
      No opt-out link or contact found in this privacy policy.
    </p>
  );
}
