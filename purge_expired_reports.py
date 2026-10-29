from api import purgar_reportes_expirados


if __name__ == "__main__":
    en_cola, eliminados = purgar_reportes_expirados()
    print(
        f"Purga terminada: {en_cola} reportes vencidos encolados; "
        f"{eliminados} eliminaciones físicas completadas."
    )
