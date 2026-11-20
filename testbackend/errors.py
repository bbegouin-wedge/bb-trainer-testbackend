"""Les erreurs du pilotage, chacune avec son code HTTP."""


class PilotError(Exception):
    status = 500


class InvalidInput(PilotError):
    """Une entrée mal formée : 422."""

    status = 422


class UnknownGame(PilotError):
    """Aucun match sous cet identifiant : 404, avec le texte d'automaton."""

    status = 404

    def __init__(self, game_id: str) -> None:
        super().__init__(f"le dossier {game_id} n'existe pas")


class Conflict(PilotError):
    """L'action ne s'applique pas à l'état du match : 409."""

    status = 409
