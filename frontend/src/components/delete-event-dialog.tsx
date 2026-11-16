import { toast } from "sonner"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { useDeleteEvent, type CalendarEvent } from "@/lib/api"

/** Asks an admin to confirm deleting an event, then deletes it. */
export function DeleteEventDialog({
  event,
  open,
  onOpenChange,
  onDeleted,
}: {
  event: CalendarEvent
  open: boolean
  onOpenChange: (open: boolean) => void
  onDeleted?: () => void
}) {
  const remove = useDeleteEvent()
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete “{event.title}”?</AlertDialogTitle>
          <AlertDialogDescription>
            It disappears from the calendar, with everyone's answers. This can't be undone.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Keep it</AlertDialogCancel>
          <AlertDialogAction
            className="bg-destructive text-white hover:bg-destructive/90"
            onClick={() =>
              remove.mutate(event.id, {
                onSuccess: () => {
                  toast.success("Event deleted")
                  onDeleted?.()
                },
                onError: (err) => toast.error(err.message),
              })
            }
          >
            Delete
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
