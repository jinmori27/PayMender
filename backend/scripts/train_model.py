from app.ml import ARTIFACT_PATH, recovery_model


if __name__ == "__main__":
    recovery_model.train(save=True)
    print(f"Saved interpretable recovery model to {ARTIFACT_PATH}")
