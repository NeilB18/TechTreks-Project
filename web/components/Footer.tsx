import { SITE_NAME } from "@/lib/site";

export function Footer() {
  return (
    <footer className="relative mx-auto mt-auto flex w-full max-w-2xl flex-col gap-1 px-5 pt-12 pb-8 text-[13px] leading-normal text-muted">
      <p>No money moves through {SITE_NAME}.</p>
      <p>Powered by GroupMe®. {SITE_NAME} isn&rsquo;t built or endorsed by GroupMe.</p>
    </footer>
  );
}
