from multigas import read_file
from multigas.data import MultiGasData
from multigas.logging import logger


def main(verbose: bool = False):
    files = [
        {
            "type": "6h",
            "filepath": r"D:\Data\Multigas Tangkuban Parahu\TANG_RTU\TANG_RTU_Data_6Hr.dat",
        },
        {
            "type": "2s",
            "filepath": r"D:\Data\Multigas Tangkuban Parahu\TANG_RTU\TANG_RTU_ChemData_Sec2.dat",
        },
    ]

    data: list[MultiGasData] = []
    for file in files:
        try:
            logger.info(f"Loading {file['filepath']}")
            multigas_data = read_file(
                file_path=file["filepath"],
                dataset_type=file["type"],
                use_cache=True,
                verbose=verbose,
            )
            data.append(multigas_data)
            logger.info(f"Loaded: {multigas_data.__repr__()}")
        except Exception as e:
            logger.warning(f"Could not parse {file['filepath']}. {e}")
            continue

    if len(data) == 0:
        logger.error("No data found")


if __name__ == "__main__":
    main(True)
