from multigas import read_file
from multigas.logging import logger


def main(n_jobs: int = 1, verbose: bool = False):
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

    for file in files:
        try:
            logger.info(f"Loading {file['filepath']}")
            data = read_file(
                file_path=file["filepath"],
                dataset_type=file["type"],
                use_cache=True,
                verbose=verbose,
            )
            logger.info(f"Loaded: {data.__repr__()}")
            data.extract_daily(n_jobs=n_jobs)
        except Exception as e:
            logger.warning(f"Could not parse {file['filepath']}. {e}")
            continue


if __name__ == "__main__":
    main(n_jobs=8, verbose=True)
