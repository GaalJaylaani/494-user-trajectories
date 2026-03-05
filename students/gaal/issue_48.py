import marimo

__generated_with = "0.19.7"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import polars as pl
    from pathlib import Path

    BASE = Path("/Users/gaaljaylaani/494-user-trajectories")
    # Note: filenames are swapped — "notes" file has ratings rows, "ratings" file has notes rows
    RATINGS_PATH     = BASE / "local-data/ISSUE6/notes-20240501-20240531.parquet"
    NOTES_PATH       = BASE / "local-data/ISSUE6/ratings-20240501-20240531.parquet"
    PARTY_TOPIC_PATH = BASE / "local-data/ISSUE6/database_replication.csv"

    # ratings cols: noteId, ratedOnTweetId, raterParticipantId, helpfulnessLevel,
    #               noteFinalRatingStatus, noteFinalIntercept, noteFinalFactor
    # notes cols:   noteId, tweetId, noteAuthorParticipantId, classification, summary,
    #               noteFinalRatingStatus, noteFinalIntercept, noteFinalFactor
    ratings = pl.read_parquet(RATINGS_PATH)
    notes   = pl.read_parquet(NOTES_PATH)

    # Tweet-level lookup: tweet_id → party (enc), topic
    db_tweet = (
        pl.read_csv(PARTY_TOPIC_PATH, columns=["tweet_id", "party", "topic"])
        .unique(subset=["tweet_id"], keep="first")
        .with_columns(
            pl.when(pl.col("party") == "republican").then(-1)
              .when(pl.col("party") == "democrat").then(1)
              .otherwise(None).cast(pl.Float64).alias("party_enc")
        )
    )

    ratings_full = ratings.join(db_tweet, left_on="ratedOnTweetId", right_on="tweet_id", how="left")
    notes_full   = notes.join(db_tweet, left_on="tweetId", right_on="tweet_id", how="left")
    return mo, notes_full, pl, ratings_full


@app.cell
def _(mo, notes_full, pl, ratings_full):
    def _shannon_entropy(series):
        vals = series.drop_nulls()
        if len(vals) == 0:
            return float("nan")
        counts = vals.value_counts().get_column("count").cast(pl.Float64)
        probs = counts / counts.sum()
        return float(-(probs * probs.log(base=2)).sum())

    # ── Partisanship signals ───────────────────────────────────────────────────
    partisanship_rater = (
        ratings_full
        .group_by("raterParticipantId")
        .agg([
            pl.col("party_enc").mean().alias("avg_party_rated"),
            pl.col("party_enc").filter(pl.col("helpfulnessLevel") == "HELPFUL").mean().alias("avg_party_rated_helpful"),
            pl.col("party_enc").filter(pl.col("helpfulnessLevel") == "NOT_HELPFUL").mean().alias("avg_party_rated_not_helpful"),
            pl.col("noteFinalFactor").filter(pl.col("helpfulnessLevel") == "HELPFUL").mean().alias("avg_note_factor_helpful"),
            pl.col("noteFinalFactor").filter(pl.col("helpfulnessLevel") == "NOT_HELPFUL").mean().alias("avg_note_factor_not_helpful"),
            (pl.col("party") == "republican").mean().alias("pct_republican_rated"),
            (pl.col("party").filter(pl.col("helpfulnessLevel") == "HELPFUL") == "republican").mean().alias("pct_republican_rated_helpful"),
            (pl.col("party").filter(pl.col("helpfulnessLevel") == "NOT_HELPFUL") == "republican").mean().alias("pct_republican_rated_not_helpful"),
        ])
        .rename({"raterParticipantId": "participantId"})
    )

    partisanship_author = (
        notes_full
        .group_by("noteAuthorParticipantId")
        .agg([
            pl.col("party_enc").mean().alias("avg_party_wrote_about"),
            (pl.col("party") == "republican").mean().alias("pct_republican_wrote_about"),
        ])
        .rename({"noteAuthorParticipantId": "participantId"})
    )

    # ── Interest signals ───────────────────────────────────────────────────────
    interest_rated = (
        ratings_full
        .group_by("raterParticipantId")
        .agg(pl.col("topic").drop_nulls().n_unique().alias("n_unique_topics_rated"))
        .rename({"raterParticipantId": "participantId"})
    )

    interest_wrote = (
        notes_full
        .group_by("noteAuthorParticipantId")
        .agg(pl.col("topic").drop_nulls().n_unique().alias("n_unique_topics_wrote"))
        .rename({"noteAuthorParticipantId": "participantId"})
    )

    entropy_rated = (
        ratings_full
        .group_by("raterParticipantId")
        .map_groups(lambda df: df.head(1)
                    .select("raterParticipantId")
                    .with_columns(pl.lit(_shannon_entropy(df["topic"])).alias("topic_entropy_rated")))
        .rename({"raterParticipantId": "participantId"})
    )

    entropy_wrote = (
        notes_full
        .group_by("noteAuthorParticipantId")
        .map_groups(lambda df: df.head(1)
                    .select("noteAuthorParticipantId")
                    .with_columns(pl.lit(_shannon_entropy(df["topic"])).alias("topic_entropy_wrote")))
        .rename({"noteAuthorParticipantId": "participantId"})
    )

    # ── Skill signals ──────────────────────────────────────────────────────────
    skill_signals = (
        notes_full
        .group_by("noteAuthorParticipantId")
        .agg([
            pl.col("noteFinalIntercept").mean().alias("avg_note_intercept_wrote"),
            (pl.col("noteFinalRatingStatus") == "CURRENTLY_RATED_HELPFUL").mean().alias("pct_notes_helpful"),
        ])
        .rename({"noteAuthorParticipantId": "participantId"})
    )

    agreement_signals = (
        ratings_full
        .with_columns(
            pl.when(
                ((pl.col("helpfulnessLevel") == "HELPFUL") & (pl.col("noteFinalRatingStatus") == "CURRENTLY_RATED_HELPFUL")) |
                ((pl.col("helpfulnessLevel") == "NOT_HELPFUL") & (pl.col("noteFinalRatingStatus") == "CURRENTLY_RATED_NOT_HELPFUL"))
            ).then(1).otherwise(0).alias("agreed")
        )
        .group_by("raterParticipantId")
        .agg(pl.col("agreed").mean().alias("pct_ratings_agreed"))
        .rename({"raterParticipantId": "participantId"})
    )

    activity = (
        ratings_full
        .group_by("raterParticipantId")
        .agg(pl.len().alias("n_ratings"))
        .rename({"raterParticipantId": "participantId"})
        .join(
            notes_full
            .group_by("noteAuthorParticipantId")
            .agg(pl.len().alias("n_notes"))
            .rename({"noteAuthorParticipantId": "participantId"}),
            on="participantId", how="full", coalesce=True,
        )
    )

    # ── Final user-level signals table ─────────────────────────────────────────
    user_signals = (
        partisanship_rater
        .join(partisanship_author,  on="participantId", how="full", coalesce=True)
        .join(interest_rated,       on="participantId", how="full", coalesce=True)
        .join(interest_wrote,       on="participantId", how="full", coalesce=True)
        .join(entropy_rated,        on="participantId", how="full", coalesce=True)
        .join(entropy_wrote,        on="participantId", how="full", coalesce=True)
        .join(skill_signals,        on="participantId", how="full", coalesce=True)
        .join(agreement_signals,    on="participantId", how="full", coalesce=True)
        .join(activity,             on="participantId", how="full", coalesce=True)
    )

    mo.vstack([
        mo.md(f"**{len(user_signals):,} users** | **{len(user_signals.columns)} signal columns**"),
        mo.ui.table(user_signals),
    ])


if __name__ == "__main__":
    app.run()
