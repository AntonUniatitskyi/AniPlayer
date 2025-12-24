from django.apps import AppConfig


class MyanimeConfig(AppConfig):
    name = "myanime"
    def ready(self):
        import myanime.signals
