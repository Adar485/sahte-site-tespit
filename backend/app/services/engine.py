"""Analysis engine boundary.

The real engine (URL, screenshot, text and DOM analysis combined by XGBoost)
is not implemented yet. Until it is, submit() raises AnalysisEngineUnavailable
and callers record the request as failed with error_code "service_unavailable".
No scores, findings or results are fabricated here.
"""

ENGINE_UNAVAILABLE_MESSAGE = (
    "Analiz motoru henüz kullanıma hazır değil. İstek kaydedildi, ancak sayfa incelenmedi "
    "ve risk değerlendirmesi yapılmadı."
)


class AnalysisEngineUnavailable(RuntimeError):
    def __init__(self, message: str = ENGINE_UNAVAILABLE_MESSAGE) -> None:
        super().__init__(message)


def is_available() -> bool:
    return False


def submit(analysis_id: str, url: str) -> None:
    """Hand an analysis to the engine. Replace with the real runner later.

    The future implementation should start the work (for example in a
    background worker), set the analysis to "running", and later write the
    final status, risk and module results.
    """
    raise AnalysisEngineUnavailable()
