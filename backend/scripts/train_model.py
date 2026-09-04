from app.ml import recovery_model


if __name__ == "__main__":
    recovery_model.train()
    print("Trained the deterministic recovery model in memory; no executable artifact was written.")
