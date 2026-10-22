import Link from "next/link";

export default function TripNotFound() {
  return (
    <main className="mx-auto w-full max-w-2xl px-4 py-16 text-center">
      <h1 className="text-xl font-semibold">Trip not found</h1>
      <p className="mt-2 text-muted">Check the link @tripbot posted in your group chat.</p>
      <Link href="/" className="mt-6 inline-block text-accent underline">
        Back to trips
      </Link>
    </main>
  );
}
