// Shown while the trip page loads: grey blocks in the page's shape (design canvas: "New trip: empty and loading").
export default function TripLoading() {
  const block = "block animate-pulse rounded-[22px] bg-surface";
  return (
    <main id="main" aria-busy="true" aria-label="Loading the trip" className="mx-auto flex w-full max-w-2xl flex-col gap-3.5 px-5 pt-[74px]">
      <span className={`${block} h-[150px]`} />
      <span className={`${block} mt-4 h-10 w-3/4 rounded-xl`} />
      <span className={`${block} h-4 w-1/2 rounded-lg`} />
      <span className={`${block} mt-6 h-[180px]`} />
      <span className={`${block} h-16`} />
      <span className={`${block} h-16`} />
    </main>
  );
}
