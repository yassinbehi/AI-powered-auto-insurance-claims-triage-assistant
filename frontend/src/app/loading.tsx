import { PageContainer } from "@/components/layout/page-container";
import { Skeleton } from "@/components/ui/skeleton";

/** Squelette a la forme reelle de la page, et non un indicateur tournant :
 *  la mise en page ne doit pas sauter a l'arrivee des donnees. */
export default function Loading() {
  return (
    <PageContainer className="space-y-8" aria-busy="true">
      <div className="space-y-2">
        <Skeleton className="h-8 w-56" />
        <Skeleton className="h-4 w-full max-w-2xl" />
      </div>
      <div className="space-y-px rounded-lg border p-4">
        {Array.from({ length: 8 }).map((_, index) => (
          <Skeleton key={index} className="h-12 w-full" />
        ))}
      </div>
    </PageContainer>
  );
}
