# Synthetic accepted estimates for routing/editing demos; no statistical model.
library(ggplot2)
estimates <- data.frame(
  label = c("Group A", "Group B", "Group C"),
  estimate = c(0.9, 1.2, 1.05),
  low = c(0.7, 0.95, 0.82),
  high = c(1.1, 1.45, 1.28)
)
p <- ggplot(estimates, aes(x = estimate, y = label)) +
  geom_segment(aes(x = low, xend = high, yend = label)) +
  geom_point(size = 2, colour = "#276D55") +
  geom_vline(xintercept = 1, linetype = "dashed") +
  theme_classic(base_size = 10) + labs(x = "Accepted estimate", y = NULL)
# Call ggsave explicitly in a real authorized rendering task.
