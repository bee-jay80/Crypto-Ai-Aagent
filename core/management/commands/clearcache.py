from django.core.management.base import BaseCommand
from django.core.cache import cache


class Command(BaseCommand):
    help = (
        "Clear Django cache.\n"
        "By default this will clear the entire cache. Use --keys key1 key2 to delete specific keys."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--keys",
            nargs="*",
            help="List of cache keys to delete. If omitted, the entire cache will be cleared.",
        )
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Confirm destructive operations (required when clearing entire cache).",
        )

    def handle(self, *args, **options):
        keys = options.get("keys")
        confirm = options.get("confirm")

        if keys:
            self.stdout.write(self.style.NOTICE(f"Deleting {len(keys)} key(s) from cache..."))
            for k in keys:
                ok = cache.delete(k)
                self.stdout.write(self.style.SUCCESS(f"Deleted key: {k} -> {ok}"))
            self.stdout.write(self.style.SUCCESS("Done."))
            return

        # No keys specified: clear entire cache
        self.stdout.write(self.style.WARNING("About to clear the entire cache."))
        if not confirm:
            self.stdout.write(self.style.ERROR("Operation aborted. Re-run with --confirm to proceed."))
            return

        try:
            cache.clear()
            self.stdout.write(self.style.SUCCESS("Cache cleared."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to clear cache: {e}"))
