set terminal svg size 1000,560 enhanced font 'Arial,16' background rgb '#ffffff' # Render numerical evidence with the native Gnuplot executable.
set output 'failed_dynamic_equilibrium.svg' # Keep a reusable vector figure alongside the original data.
set title "Detailed Zhaqing bridge: failed wind-history equilibrium check\n30,555 nodes | Planned history: 20 s | Complete training epochs: 0" font ',16' # State both the actual mesh and incomplete status using an actual rendered line break.
set xlabel 'Physical time (s)' # Display real solver time rather than wall-clock training time.
set ylabel 'Maximum equivalent free residual (N)' # Use the independent force-and-scaled-moment equilibrium audit.
set xrange [0:0.095] # Restrict the axis to the actual attempted portion of the failed history.
set yrange [0:0.027] # Keep the rejected residual and the original acceptance threshold visible.
set xtics 0.02 # Provide readable physical-time tick labels.
set ytics 0.005 # Keep absolute residual magnitudes directly readable.
set grid back lc rgb '#e2e8f0' # Add a restrained scientific reference grid.
set border 3 lc rgb '#334155' # Avoid an unnecessary heavy box around the data.
set tics nomirror # Show ticks only on the labeled axes.
set key left top spacing 1.2 # Keep labels away from the rejected point at the right edge.
set label 1 'Step 14 rejected: 0.02219 N' at 0.046,0.025 tc rgb '#b91c1c' # Explain the actual failed gate without inventing a response result.
set label 2 '13 accepted dynamic steps; no complete training history' at 0.006,0.012 font ',14' tc rgb '#475569' # Distinguish accepted partial steps from a usable learning sample.
plot 'failed_dynamic_equilibrium.dat' using 1:($3 == 1 ? $2 : 1/0) with linespoints lw 2.5 pt 7 ps 0.8 lc rgb '#2563eb' title 'Accepted native audits', 0.02 with lines lw 2 dt 2 lc rgb '#d97706' title 'Required gate: 0.020 N', 'failed_dynamic_equilibrium.dat' using 1:($3 == 0 ? $2 : 1/0) with points pt 2 ps 1.8 lw 3 lc rgb '#dc2626' title 'Rejected native audit' # Plot only extracted original solver evidence and its unchanged threshold.
