__all__ = ["StudentExportService"]


def __getattr__(name: str):
    if name == "StudentExportService":
        from quantfish.student_exports.service import StudentExportService

        return StudentExportService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
