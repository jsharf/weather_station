import logging
import matplotlib.pyplot as plt

from co2_samples import *

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger.info(f"Loading cache...")
    co2_samples = get_entire_co2_ppm_cache()
    co2_samples = [sample for sample in co2_samples if sample.timestamp > datetime.now() - timedelta(days=3650)]
    logger.info(f"Plotting...")
    fig = co2_ppm_graph_image(co2_samples)
    # Show fig.
    plt.show()