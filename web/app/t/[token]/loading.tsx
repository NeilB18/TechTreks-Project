import { SITE_NAME } from "@/lib/site";

// Shown while a trip page loads (design canvas: Final designs, "Loading"): grey blocks in the
// page's own shape, so nothing jumps when it arrives.
export default function TripLoading() {
  const block = "block rounded-md bg-white/10";
  return (
    <main id="main" aria-busy="true" className="mx-auto w-full max-w-2xl motion-safe:animate-pulse">
      <div className="relative h-[300px] bg-raised">
        <p className="wide px-5 py-1.5 text-lg"><span className="inline-flex min-h-11 items-center">{SITE_NAME.toLowerCase()}</span></p>
        <div aria-hidden="true" className="absolute inset-x-0 top-[110px] flex flex-col items-center gap-3">
          <span className={`${block} h-[22px] w-[70px] rounded-lg`} />
          <span className={`${block} h-9 w-[260px] rounded-[10px] bg-white/12`} />
          <span className={`${block} h-[18px] w-[120px] rounded-lg`} />
        </div>
      </div>
      <div aria-hidden="true" className="mx-5 mt-2.5 h-[52px] rounded-full bg-white/8" />
      <div aria-hidden="true" className="flex flex-col gap-4.5 px-5 pt-5.5">
        {[210, 150, 180].map((w) => (
          <div key={w} className="flex items-center gap-3.5">
            <span className={`${block} size-[22px]`} />
            <span className={`${block} h-4`} style={{ width: w }} />
          </div>
        ))}
      </div>
      <div aria-hidden="true" className="mx-3.5 mt-6.5 h-[170px] rounded-[22px] bg-white/6" />
      <p role="status" className="mx-5 mt-5.5 text-sm text-muted">Loading the trip…</p>
    </main>
  );
}
