"""Synthetic accepted ROC coordinates: an editing fixture, with no training."""
import matplotlib.pyplot as plt

fpr = [0.0, 0.1, 0.3, 0.6, 1.0]
tpr = [0.0, 0.4, 0.7, 0.9, 1.0]
fig, ax = plt.subplots(figsize=(3.5, 3.0))
ax.plot(fpr, tpr, color="#276D55", label="Accepted ROC")
ax.plot([0, 1], [0, 1], color="0.7", linestyle="--")
ax.set(xlabel="False positive rate", ylabel="True positive rate")
ax.legend(loc="lower right")
# Save explicitly in a real authorized rendering task.
