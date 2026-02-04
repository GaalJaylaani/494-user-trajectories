import marimo

__generated_with = "0.19.7"
app = marimo.App(width="medium")


@app.cell
def _():
    import polars as pl
    return (pl,)


@app.cell
def _(pl):
    notes = pl.read_csv("/Users/gaaljaylaani/494-user-trajectories/data/filtered/2023-10/notes/notes-00000.tsv", separator="\t")
    scored = pl.read_csv("/Users/gaaljaylaani/494-user-trajectories/students/gaal/output/scored_notes.tsv", separator="\t")
    ratings = pl.read_csv("/Users/gaaljaylaani/494-user-trajectories/students/gaal/output/merged_ratings.tsv", separator="\t")
    return notes, scored


@app.cell
def _(notes, scored):
    notes_with_scores = notes.join(scored, on="noteId", how="inner")
    return (notes_with_scores,)


@app.cell
def _(notes_with_scores):
    notes_with_scores.select([
        "noteId", 
        "summary",
        "classification",
        "coreNoteIntercept",
        "finalRatingStatus"
    ]).head(1000)
    return


if __name__ == "__main__":
    app.run()
