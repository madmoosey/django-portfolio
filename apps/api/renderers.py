from rest_framework_csv.renderers import CSVRenderer


class ExportCSVRenderer(CSVRenderer):
    """
    Custom CSV Renderer.
    Override this per-viewset if specific header labels/ordering are needed.
    """

    header = None
